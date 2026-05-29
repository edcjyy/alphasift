# -*- coding: utf-8 -*-
"""Reflection Mutator — apply LLM-proposed changes to strategy YAML files."""

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
    
    Raises KeyError if any intermediate key is missing.
    """
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
    """Parse string value to int/float/str as appropriate."""
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
) -> dict:
    """Apply validated changes to a strategy YAML file.

    Args:
        strategy_path: Path to the strategy .yaml file
        changes: List of StrategyChange objects to apply
        dry_run: If True, return what would change without modifying files
        min_confidence: Minimum LLM confidence to auto-apply a change
        auto_backup: If True, create a .bak copy before modifying

    Returns:
        dict with keys: applied (list of applied changes), skipped (list of skipped),
        backup_path (if created), new_path (if saved as new file)
    """
    if not changes:
        return {"applied": [], "skipped": [], "message": "No changes to apply"}

    # Read original YAML
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
        # Validate confidence
        if change.confidence < min_confidence:
            skipped.append({
                "change": change,
                "reason": f"LLM 置信度 {change.confidence:.2f} < 阈值 {min_confidence}",
            })
            continue

        # Resolve target path
        try:
            parent, key = _resolve_yaml_path(screening, change.target)
        except Exception as e:
            skipped.append({"change": change, "reason": f"路径解析失败: {e}"})
            continue

        # Parse new value
        new_val = _parse_value(change.new_value)

        # Record old value
        if isinstance(parent, dict) and key in parent:
            change.old_value = str(parent[key])
        else:
            skipped.append({"change": change, "reason": f"目标键 '{key}' 不存在"})
            continue

        # Apply
        if dry_run:
            applied.append(change)
        else:
            parent[key] = new_val
            applied.append(change)

    if dry_run:
        return {
            "applied": applied,
            "skipped": skipped,
            "message": f"dry-run: 将应用 {len(applied)} 个修改, 跳过 {len(skipped)} 个",
        }

    # Save
    if auto_backup:
        backup_path = strategy_path.with_suffix(".yaml.bak")
        shutil.copy2(strategy_path, backup_path)
        logger.info("Backed up to %s", backup_path)
    else:
        backup_path = None

    # Write modified YAML
    new_yaml = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
    strategy_path.write_text(new_yaml, encoding="utf-8")

    logger.info(
        "Applied %d changes to %s (skipped %d)", len(applied), strategy_path.name, len(skipped)
    )

    return {
        "applied": applied,
        "skipped": skipped,
        "backup_path": str(backup_path) if backup_path else None,
        "new_path": str(strategy_path),
        "message": f"应用 {len(applied)} 个修改, 跳过 {len(skipped)} 个",
    }
