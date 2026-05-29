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
from alphasift.reflection.critic import validate_changes
from alphasift.reflection.experience import (
    get_change_history,
    save_reflection,
)
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
    auto_reevaluate: bool = False,
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

    # 5. Critic: validate changes before applying
    category = "framework"
    if yaml_path:
        try:
            import yaml
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            category = data.get("category", "framework") if isinstance(data, dict) else "framework"
        except Exception:
            pass

    # Load change history for duplication check
    history = {}
    if data_dir:
        try:
            history = get_change_history(strategy_name, data_dir=data_dir)
        except Exception:
            logger.debug("Could not load change history (first run?)", exc_info=True)

    critic_result = validate_changes(
        changes=result.changes,
        strategy_category=category,
        strategy_name=strategy_name,
        history=history,
        min_confidence=min_confidence,
    )

    logger.info(
        "Critic: passed=%d warned=%d rejected=%d score=%.2f",
        len(critic_result.passed),
        len(critic_result.warned),
        len(critic_result.rejected),
        critic_result.score,
    )

    # 6. Mutator: apply validated changes
    mutation_result = {"applied": [], "skipped": []}
    if (apply or dry_run) and critic_result.passed and yaml_path:
        mutation_result = apply_changes(
            strategy_path=yaml_path,
            changes=critic_result.passed,
            dry_run=dry_run,
            min_confidence=0.0,  # Already validated by critic
            auto_backup=not dry_run,
        )
        logger.info(
            "Mutation: applied=%d skipped=%d",
            len(mutation_result["applied"]),
            len(mutation_result["skipped"]),
        )

    # 7. Experience: save reflection record
    if data_dir and not dry_run:
        try:
            save_reflection(
                result,
                data_dir=data_dir,
                strategy_category=category,
                critic_score=critic_result.score,
                passed_count=len(critic_result.passed),
                rejected_count=len(critic_result.rejected),
            )
            logger.info("Reflection saved to experience store")
        except Exception as e:
            logger.warning("Failed to save reflection: %s", e)

    # 8. Auto re-evaluate: screen + evaluate with new strategy
    if auto_reevaluate and apply and not dry_run and critic_result.passed:
        try:
            logger.info("Auto re-evaluating with modified strategy: %s", strategy_name)
            from alphasift.pipeline import screen as run_screen
            new_result = run_screen(strategy_name, max_output=5, use_llm=False)
            if new_result and new_result.run_id:
                from alphasift.store import save_screen_result
                save_screen_result(new_result, data_dir=data_dir)
                from alphasift.evaluate import evaluate_saved_run
                from alphasift.store import save_evaluation_result
                eval_result2 = evaluate_saved_run(new_result.run_id, config=config)
                save_evaluation_result(eval_result2, data_dir=data_dir)

                # Update outcome in experience store
                improved = (
                    eval_result2.win_rate is not None
                    and result.win_rate is not None
                    and eval_result2.win_rate > result.win_rate
                )
                from alphasift.reflection.experience import update_outcome
                # Find the last saved record for this strategy
                records = get_history(strategy_name, data_dir=data_dir, limit=1)
                if records:
                    update_outcome(
                        records[0]["id"], data_dir=data_dir,
                        after_run_id=new_result.run_id,
                        win_rate_after=eval_result2.win_rate,
                        avg_return_after=eval_result2.average_return_pct,
                        improved=improved,
                    )
                logger.info(
                    "Auto re-evaluate: win_rate %.1f%% → %.1f%% (%s)",
                    (result.win_rate or 0) * 100,
                    (eval_result2.win_rate or 0) * 100,
                    "improved" if improved else "no improvement",
                )
        except Exception as e:
            logger.warning("Auto re-evaluate failed: %s", e)

    return result
