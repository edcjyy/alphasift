# -*- coding: utf-8 -*-
"""Reflection Mutator — apply LLM-proposed changes to strategy YAML files.

Features: change application, version tracking, rollback.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

from alphasift.reflection.models import StrategyChange

logger = logging.getLogger(__name__)
_TZ_SHANGHAI = timezone(timedelta(hours=8))


def _now() -> str:
    return datetime.now(_TZ_SHANGHAI).isoformat()


def _resolve_yaml_path(data: dict, path: str) -> tuple[dict, str]:
    """Resolve dotted path in nested dict. Returns (parent_dict, key_name).
    Raises KeyError if any intermediate key is missing."""
    parts = path.split(".")
    current = data
    for part in parts[:-1]:
        if part not in current:
            raise KeyError(f"Path component '{part}' not found in {path}")
        current = current[part]
        if not isinstance(current, dict):
            raise TypeError(f"Path component '{part}' is not a dict in {path}")
    return current, parts[-1]


def _parse_value(val: str) -> int | float | str:
    try:
        return int(val)
    except (ValueError, TypeError):
        pass
    try:
        return float(val)
    except (ValueError, TypeError):
        pass
    return val


def apply_changes(
    strategy_path: Path,
    changes: list[StrategyChange],
    *,
    dry_run: bool = False,
    min_confidence: float = 0.5,
    auto_backup: bool = True,
    auto_version: bool = True,
) -> dict:
    """Apply validated changes to a strategy YAML file.

    Args:
        strategy_path: Path to the strategy .yaml file
        changes: List of StrategyChange objects to apply
        dry_run: If True, return what would change without modifying files
        min_confidence: Minimum LLM confidence to auto-apply a change
        auto_backup: If True, create a .bak copy before modifying
        auto_version: If True, save a numbered version before modifying (.v1, .v2, ...)

    Returns:
        dict with keys: applied, skipped, backup_path, new_path, version, message
    """
    if not changes:
        return {"applied": [], "skipped": [], "message": "No changes to apply", "version": None}

    original_text = strategy_path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(original_text)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {strategy_path}: {e}")

    if not isinstance(data, dict) or "screening" not in data:
        raise ValueError(f"Invalid strategy file: missing 'screening' section")

    screening = data["screening"]
    applied: list[StrategyChange] = []
    skipped: list[dict] = []

    for change in changes:
        if change.confidence < min_confidence:
            skipped.append({"change": change, "reason": f"置信度 {change.confidence:.2f} < {min_confidence}"})
            continue
        try:
            parent, key = _resolve_yaml_path(screening, change.target)
        except (KeyError, TypeError) as e:
            skipped.append({"change": change, "reason": f"路径: {e}"})
            continue
        new_val = _parse_value(change.new_value)
        if isinstance(parent, dict) and key in parent:
            change.old_value = str(parent[key])
        else:
            skipped.append({"change": change, "reason": f"键 '{key}' 不存在"})
            continue
        if dry_run:
            applied.append(change)
        else:
            parent[key] = new_val
            applied.append(change)

    if dry_run:
        return {"applied": applied, "skipped": skipped,
                "message": f"dry-run: {len(applied)} 改, {len(skipped)} 跳", "version": None}

    # Version tracking — save current state as numbered version
    version_num = None
    if auto_version:
        base = strategy_path.stem
        parent_dir = strategy_path.parent
        existing = sorted(parent_dir.glob(f"{base}.v*.yaml"))
        version_num = len(existing) + 1
        version_path = parent_dir / f"{base}.v{version_num}.yaml"
        shutil.copy2(strategy_path, version_path)
        logger.info("Version saved: %s", version_path)

    if auto_backup:
        backup_path = strategy_path.with_suffix(".yaml.bak")
        shutil.copy2(strategy_path, backup_path)
    else:
        backup_path = None

    new_yaml_str = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
    strategy_path.write_text(new_yaml_str, encoding="utf-8")

    logger.info("Applied %d changes v%d to %s", len(applied), version_num, strategy_path.name)
    return {
        "applied": applied, "skipped": skipped,
        "backup_path": str(backup_path) if backup_path else None,
        "new_path": str(strategy_path), "version": version_num,
        "message": f"应用 {len(applied)} 改 (v{version_num}), 跳过 {len(skipped)}",
    }


def rollback_strategy(strategy_path: Path, to_version: int | None = None) -> dict:
    """Roll back a strategy to a previous numbered version.

    Args:
        strategy_path: Current strategy .yaml file
        to_version: Version number to roll back to. None = roll back one.

    Returns:
        dict with restored_version, current_version, backup_of_current, message
    """
    base = strategy_path.stem
    parent_dir = strategy_path.parent
    versions = sorted(parent_dir.glob(f"{base}.v*.yaml"))
    if not versions:
        return {"error": "No previous versions found"}

    target = versions[-1] if to_version is None else parent_dir / f"{base}.v{to_version}.yaml"
    if not target.exists():
        return {"error": f"Version v{to_version} not found"}

    current_ver = len(versions)
    # Save current before rollback
    current_bak = parent_dir / f"{base}.v{current_ver + 1}.yaml"
    shutil.copy2(strategy_path, current_bak)
    strategy_path.write_text(target.read_text(encoding="utf-8"))
    restored = int(target.stem.split(".v")[-1])

    logger.info("Rollback %s: v%d → v%d", strategy_path.name, current_ver, restored)
    return {
        "restored_version": restored, "current_version": current_ver,
        "backup_of_current": str(current_bak),
        "message": f"已回滚到 v{restored}",
    }


def list_versions(strategy_path: Path) -> list[dict]:
    """List all numbered versions of a strategy."""
    base = strategy_path.stem
    parent_dir = strategy_path.parent
    return [
        {"version": i, "path": str(vp), "size": vp.stat().st_size}
        for i, vp in enumerate(sorted(parent_dir.glob(f"{base}.v*.yaml")), 1)
    ]
