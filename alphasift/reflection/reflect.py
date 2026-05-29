# -*- coding: utf-8 -*-
"""Reflection — main entry point for strategy evolution analysis.

Usage:
    # Analyze a saved evaluation run
    alphasift reflect <run_id>

    # Analyze and auto-apply changes (with confidence gate)
    alphasift reflect <run_id> --apply

    # Dry-run to preview changes
    alphasift reflect <run_id> --dry-run
"""

from __future__ import annotations

import logging
from pathlib import Path

from alphasift.reflection.analyzer import analyze_evaluation
from alphasift.reflection.models import ReflectionResult
from alphasift.reflection.mutator import apply_changes

logger = logging.getLogger(__name__)


def reflect_on_evaluation(
    *,
    run_id: str,
    data_dir: Path | None = None,
    model: str | None = None,
    strategy_dir: Path | None = None,
    apply: bool = False,
    dry_run: bool = False,
    min_confidence: float = 0.5,
) -> ReflectionResult:
    """Run reflection analysis on a saved evaluation run.

    1. Load evaluation result from data store
    2. Load corresponding strategy YAML
    3. Send to LLM for diagnosis and change proposals
    4. Optionally apply changes to strategy file

    Args:
        run_id: Saved run ID to evaluate
        data_dir: AlphaSift data directory
        model: LLM model override
        strategy_dir: Strategies directory override
        apply: If True, apply validated changes to strategy YAML
        dry_run: If True, preview changes without modifying files
        min_confidence: Minimum LLM confidence to apply a change

    Returns:
        ReflectionResult with diagnosis and proposed changes
    """
    from alphasift.config import Config
    from alphasift.store import load_screen_result, load_evaluation_result

    config = Config.from_env()
    data_dir = data_dir or config.data_dir
    strategy_dir = strategy_dir or config.strategies_dir

    # 1. Load evaluation result
    logger.info("Loading evaluation: run_id=%s", run_id)
    try:
        eval_result = load_evaluation_result(run_id, data_dir=data_dir)
    except Exception as e:
        logger.error("Failed to load evaluation: %s", e)
        return ReflectionResult(
            run_id=run_id,
            strategy="unknown",
            evaluated_at="",
            diagnosis=f"无法加载评估记录: {e}",
            summary="加载失败",
        )

    strategy_name = eval_result.strategy

    # 2. Find strategy YAML file
    yaml_path: Path | None = None
    for ext in (".yaml", ".yml"):
        candidate = strategy_dir / f"{strategy_name}{ext}"
        if candidate.exists():
            yaml_path = candidate
            break

    if yaml_path is None:
        # Search by strategy name inside YAML content
        for f in sorted(strategy_dir.glob("*.yaml")):
            try:
                import yaml
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("name") == strategy_name:
                    yaml_path = f
                    break
            except Exception:
                continue

    if yaml_path is None:
        logger.warning("Strategy YAML not found: %s", strategy_name)
        strategy_yaml = f"# Strategy '{strategy_name}' YAML not found in {strategy_dir}"
    else:
        strategy_yaml = yaml_path.read_text(encoding="utf-8")

    # 3. Extract top/bottom picks for context
    picks_sorted = sorted(
        eval_result.picks,
        key=lambda p: p.return_pct if p.return_pct is not None else -999,
        reverse=True,
    )
    winners = picks_sorted[:3]
    losers = picks_sorted[-3:] if len(picks_sorted) >= 3 else []

    # 4. Run LLM analysis
    result = analyze_evaluation(
        strategy_name=strategy_name,
        strategy_yaml=strategy_yaml,
        win_rate=eval_result.win_rate,
        avg_return_pct=eval_result.average_return_pct,
        elapsed_days=eval_result.elapsed_days,
        win_count=sum(1 for p in eval_result.picks if (p.return_pct or 0) >= 0),
        loss_count=sum(1 for p in eval_result.picks if (p.return_pct or 0) < 0),
        pick_count=len(eval_result.picks),
        winners=[
            {
                "name": p.name,
                "code": p.code,
                "return_pct": p.return_pct or 0,
                "sector": p.llm_sector or "?",
                "score": p.final_score,
            }
            for p in winners
        ],
        losers=[
            {
                "name": p.name,
                "code": p.code,
                "return_pct": p.return_pct or 0,
                "sector": p.llm_sector or "?",
                "score": p.final_score,
            }
            for p in losers
        ],
        model=model,
    )

    result.run_id = run_id
    result.evaluated_at = eval_result.evaluated_at

    # 5. Apply changes if requested
    if (apply or dry_run) and result.changes and yaml_path:
        mutation_result = apply_changes(
            strategy_path=yaml_path,
            changes=result.changes,
            dry_run=dry_run,
            min_confidence=min_confidence,
            auto_backup=not dry_run,
        )
        logger.info(
            "Mutation: applied=%d skipped=%d",
            len(mutation_result["applied"]),
            len(mutation_result["skipped"]),
        )

    return result
