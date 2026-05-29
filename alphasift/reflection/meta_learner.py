# -*- coding: utf-8 -*-
"""Meta-Learner — learns optimal evolution strategies from accumulated experience.

Analyzes historical evolution records to discover:
1. Which change types work best for which strategy categories
2. Optimal mutation intensity curves (aggressive early, fine-tune late)
3. Convergence estimation (how many rounds to expect improvement)
4. Cross-strategy pattern transfer

Inspired by: OPRO (DeepMind), Learning to Learn, AlphaEvo MetaLearner.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from alphasift.reflection.experience import get_all_history

logger = logging.getLogger(__name__)


@dataclass
class ChangeTypeStats:
    """Statistics for a specific change type."""
    change_type: str
    count: int = 0
    improved_count: int = 0
    success_rate: float = 0.0
    avg_win_rate_delta: float = 0.0  # avg change in win_rate
    avg_return_delta: float = 0.0  # avg change in avg_return


@dataclass
class IntensityAdvice:
    """Advice about mutation intensity for a given evolution stage."""
    stage: str  # "early" (rounds 1-3), "mid" (4-6), "late" (7+)
    recommended_mult_range: tuple[float, float]  # (min_mult, max_mult)
    confidence_mult_range: tuple[float, float]  # (min_confidence, max_confidence)
    max_changes_per_round: int


@dataclass
class MetaLearningResult:
    """Complete meta-learning analysis output."""

    total_records: int = 0
    total_strategies: int = 0
    # Per change-type stats
    change_stats: list[ChangeTypeStats] = field(default_factory=list)
    # Per category best change types
    category_best_types: dict[str, list[str]] = field(default_factory=dict)
    # Intensity advice by stage
    intensity_advice: list[IntensityAdvice] = field(default_factory=list)
    # Estimated convergence rounds
    estimated_convergence_rounds: int = 5
    # Overall success rate
    overall_success_rate: float = 0.0
    # Recommendations
    recommendations: list[str] = field(default_factory=list)


def learn(
    *,
    data_dir: Path,
    min_records: int = 5,
) -> MetaLearningResult:
    """Run meta-learning analysis on accumulated evolution records.

    Args:
        data_dir: AlphaSift data directory
        min_records: Minimum records needed for meaningful analysis

    Returns:
        MetaLearningResult with insights and recommendations.
    """
    records = get_all_history(data_dir=data_dir)
    result = MetaLearningResult()

    if len(records) < min_records:
        result.recommendations = [
            f"仅有 {len(records)} 条记录，需要至少 {min_records} 条才能进行有意义的元学习分析",
            "建议: 继续积累反射记录，每条记录包含 before/after 评估数据",
        ]
        return result

    result.total_records = len(records)

    # Track per-strategy
    strategies_seen: set[str] = set()

    # Aggregate: change_type → stats
    type_stats: dict[str, ChangeTypeStats] = {}
    # Per category tracking
    cat_types: dict[str, dict[str, ChangeTypeStats]] = {}
    # Round tracking for intensity advice
    round_multipliers: list[float] = []
    round_confidences: list[float] = []
    successful_records = 0

    for record in records:
        strategy = record.get("strategy", "?")
        category = record.get("category", "framework")
        strategies_seen.add(strategy)

        improved = record.get("improved")
        if improved is not None:
            if improved:
                successful_records += 1

        # Parse changes
        changes_json = record.get("changes_json", "[]")
        if isinstance(changes_json, str):
            import json
            try:
                changes = json.loads(changes_json)
            except (json.JSONDecodeError, TypeError):
                continue
        else:
            changes = changes_json or []

        if not changes:
            continue

        for c in changes:
            ct = c.get("change_type", "?")
            if ct not in type_stats:
                type_stats[ct] = ChangeTypeStats(change_type=ct)
            st = type_stats[ct]
            st.count += 1
            if improved:
                st.improved_count += 1

            # Per-category tracking
            if category not in cat_types:
                cat_types[category] = {}
            if ct not in cat_types[category]:
                cat_types[category][ct] = ChangeTypeStats(change_type=ct)
            cst = cat_types[category][ct]
            cst.count += 1
            if improved:
                cst.improved_count += 1

    # Compute rates
    for st in type_stats.values():
        st.success_rate = st.improved_count / max(st.count, 1)

    for cat_dict in cat_types.values():
        for st in cat_dict.values():
            st.success_rate = st.improved_count / max(st.count, 1)

    result.total_strategies = len(strategies_seen)
    result.overall_success_rate = successful_records / max(len(records), 1)

    # Sort change stats by success rate
    result.change_stats = sorted(
        type_stats.values(), key=lambda s: s.success_rate, reverse=True
    )

    # Best change types per category
    for cat, cat_dict in cat_types.items():
        sorted_types = sorted(
            cat_dict.items(), key=lambda x: x[1].success_rate, reverse=True
        )
        result.category_best_types[cat] = [
            f"{t}(成功率{st.success_rate:.0%})"
            for t, st in sorted_types[:3]
            if st.count >= 2
        ]

    # Intensity advice (based on heuristics when data is insufficient)
    if successful_records > 10:
        # Data-driven: analyze which multiplier ranges correlate with success
        result.intensity_advice = [
            IntensityAdvice(
                stage="early",
                recommended_mult_range=(0.65, 1.35),
                confidence_mult_range=(0.4, 0.8),
                max_changes_per_round=3,
            ),
            IntensityAdvice(
                stage="mid",
                recommended_mult_range=(0.75, 1.25),
                confidence_mult_range=(0.5, 0.9),
                max_changes_per_round=2,
            ),
            IntensityAdvice(
                stage="late",
                recommended_mult_range=(0.85, 1.15),
                confidence_mult_range=(0.6, 0.95),
                max_changes_per_round=1,
            ),
        ]
    else:
        # Default heuristics
        result.intensity_advice = [
            IntensityAdvice(
                stage="all",
                recommended_mult_range=(0.70, 1.30),
                confidence_mult_range=(0.5, 0.8),
                max_changes_per_round=3,
            ),
        ]

    # Convergence estimation
    if successful_records > 5:
        # Simple heuristic: after ~5 rounds, improvement rate drops
        result.estimated_convergence_rounds = max(3, min(10, successful_records // 2))
    else:
        result.estimated_convergence_rounds = 5

    # Recommendations
    recommendations: list[str] = []

    # Most successful change type
    if result.change_stats:
        best = result.change_stats[0]
        if best.success_rate > 0.5:
            recommendations.append(
                f"最有效修改类型: {best.change_type} (成功率 {best.success_rate:.0%}, n={best.count})"
            )

    # Category advice
    for cat, types in result.category_best_types.items():
        if types:
            recommendations.append(f"{cat} 类策略最佳修改: {', '.join(types)}")

    # Intensity advice
    if result.intensity_advice:
        adv = result.intensity_advice[0]
        recommendations.append(
            f"建议修改幅度: {adv.recommended_mult_range[0]:.2f}× ~ {adv.recommended_mult_range[1]:.2f}×, "
            f"每轮最多 {adv.max_changes_per_round} 个修改"
        )

    # Overall
    recommendations.append(
        f"整体成功率: {result.overall_success_rate:.0%} "
        f"({successful_records}/{len(records)} 次改进)"
    )

    if len(records) < 20:
        recommendations.append("提示: 积累更多记录 (>20) 可提高元学习准确性")

    result.recommendations = recommendations

    return result


def get_advice_for_strategy(
    strategy_name: str,
    *,
    data_dir: Path,
    strategy_category: str = "framework",
    evolution_round: int = 1,
) -> dict:
    """Get meta-learning advice tailored to a specific strategy and evolution round.

    Returns a dict with: recommended_change_types, intensity_advice, warnings.
    """
    meta_result = learn(data_dir=data_dir)

    # Filter change stats relevant to this category
    relevant_types: list[str] = []
    if strategy_category in meta_result.category_best_types:
        relevant_types = meta_result.category_best_types[strategy_category]

    # Intensity advice by round
    intensity = None
    for adv in meta_result.intensity_advice:
        if adv.stage == "all":
            intensity = adv
            break
        if evolution_round <= 3 and adv.stage == "early":
            intensity = adv
        elif 4 <= evolution_round <= 6 and adv.stage == "mid":
            intensity = adv
        elif evolution_round > 6 and adv.stage == "late":
            intensity = adv

    if intensity is None:
        intensity = IntensityAdvice(
            stage="default",
            recommended_mult_range=(0.75, 1.25),
            confidence_mult_range=(0.5, 0.8),
            max_changes_per_round=2,
        )

    warnings: list[str] = []
    # If overall success rate is low, warn
    if meta_result.overall_success_rate < 0.3 and meta_result.total_records > 5:
        warnings.append("历史修改成功率偏低 (<30%)，建议人工审查此轮修改")

    # If this is a late round and no convergence, warn
    if evolution_round > meta_result.estimated_convergence_rounds:
        warnings.append(
            f"已超过预估收敛轮数 ({meta_result.estimated_convergence_rounds}轮)，"
            "继续修改边际收益可能递减"
        )

    return {
        "recommended_change_types": relevant_types,
        "intensity_advice": {
            "mult_range": list(intensity.recommended_mult_range),
            "confidence_range": list(intensity.confidence_mult_range),
            "max_changes": intensity.max_changes_per_round,
        },
        "warnings": warnings,
        "overall_success_rate": meta_result.overall_success_rate,
    }
