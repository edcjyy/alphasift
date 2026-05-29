# -*- coding: utf-8 -*-
"""Reflection Critic — quality gate for strategy change proposals.

Validates LLM-proposed changes before they are applied to strategy YAML,
checking: consistency, historical duplication, feasibility, and regression risk.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from alphasift.reflection.models import StrategyChange

logger = logging.getLogger(__name__)

# Per-strategy-category guardrails: which change types are risky
_CATEGORY_RISK_MAP: dict[str, list[str]] = {
    "value": ["ADJUST_WEIGHT:momentum>1.2", "MODIFY_FILTER:pe_ttm_max>1.3"],
    "momentum": ["ADJUST_WEIGHT:stability>1.5", "MODIFY_RISK:chase_change_pct<0.6"],
    "reversal": ["ADJUST_WEIGHT:momentum>1.2", "MODIFY_FILTER:change_pct_max>1.5"],
    "trend": ["ADJUST_WEIGHT:value>1.3", "MODIFY_FILTER:turnover_rate_min<0.6"],
    "framework": [],  # framework strategies can flex more
}

# Parameter feasibility bounds (per target key)
_FEASIBILITY_BOUNDS: dict[str, tuple[float, float]] = {
    "pe_ttm_max": (5, 200),
    "pb_max": (0.5, 15),
    "amount_min": (10_000_000, 2_000_000_000),
    "change_pct_max": (3, 10.5),
    "change_pct_min": (-10.5, -0.5),
    "turnover_rate_min": (0.3, 10),
    "volume_ratio_min": (0.5, 5),
    "signal_score_min": (10, 90),
    "chase_change_pct": (3, 10),
    "high_turnover_rate": (5, 30),
    "abnormal_volume_ratio": (2, 15),
}


@dataclass
class CriticResult:
    """Output of the critic validation pass."""

    passed: list[StrategyChange] = field(default_factory=list)
    warned: list[dict] = field(default_factory=list)  # {change, warning, severity}
    rejected: list[dict] = field(default_factory=list)  # {change, reason}
    score: float = 1.0  # 0.0-1.0 quality score for the whole batch


def validate_changes(
    changes: list[StrategyChange],
    *,
    strategy_category: str = "framework",
    strategy_name: str = "",
    history: dict | None = None,  # {target: [old_attempts]} from experience store
    min_confidence: float = 0.5,
) -> CriticResult:
    """Validate a list of proposed strategy changes.

    Args:
        changes: LLM-proposed changes
        strategy_category: e.g. "value", "momentum", "framework"
        strategy_name: strategy identifier for history lookup
        history: dict of {target_key: list_of_previous_values} for dedup check
        min_confidence: minimum LLM confidence to accept

    Returns:
        CriticResult with passed/warned/rejected changes and batch score.
    """
    result = CriticResult()

    for change in changes:
        # --- Check 1: Confidence threshold ---
        if change.confidence < min_confidence:
            result.rejected.append({
                "change": change,
                "reason": f"LLM 置信度 {change.confidence:.2f} < 阈值 {min_confidence}",
            })
            continue

        # --- Check 2: Category guardrail ---
        warnings = _check_category_guardrail(change, strategy_category)
        if warnings.get("block"):
            result.rejected.append({"change": change, "reason": warnings["block"]})
            continue

        # --- Check 3: Historical duplication ---
        if history:
            dup_warning = _check_duplication(change, history)
            if dup_warning:
                result.warned.append({
                    "change": change,
                    "warning": dup_warning,
                    "severity": "low",
                })
                # Don't block — just warn

        # --- Check 4: Feasibility bounds ---
        feas_issue = _check_feasibility(change)
        if feas_issue:
            result.rejected.append({"change": change, "reason": feas_issue})
            continue

        # --- Check 5: Multiplier reasonableness ---
        mult_issue = _check_multiplier(change)
        if mult_issue:
            result.rejected.append({"change": change, "reason": mult_issue})
            continue

        # --- Check 6: Strategy category warnings ---
        cat_warn = warnings.get("warn")
        if cat_warn:
            result.warned.append({
                "change": change,
                "warning": cat_warn,
                "severity": "medium",
            })

        result.passed.append(change)

    # Batch score: penalize for rejected changes
    total = len(changes) or 1
    passed_ratio = len(result.passed) / total
    warned_penalty = len(result.warned) * 0.05
    result.score = max(0.0, min(1.0, passed_ratio - warned_penalty))

    logger.info(
        "Critic validation: passed=%d warned=%d rejected=%d score=%.2f [%s/%s]",
        len(result.passed), len(result.warned), len(result.rejected),
        result.score, strategy_name, strategy_category,
    )
    for r in result.rejected:
        logger.debug("Critic rejected: %s → %s", r["change"].target, r["reason"])

    return result


def _check_category_guardrail(
    change: StrategyChange,
    category: str,
) -> dict:
    """Check if a change violates category-specific guardrails."""
    risks = _CATEGORY_RISK_MAP.get(category, [])
    for risk in risks:
        # Format: "CHANGE_TYPE:target>threshold" or "CHANGE_TYPE:target<threshold"
        if not risk.startswith(change.change_type + ":"):
            continue
        rule = risk.split(":", 1)[1]  # e.g. "momentum>1.2"
        if ">" in rule:
            key, thresh_str = rule.split(">", 1)
            if key in change.target:
                try:
                    # Check if the multiplier (new/old) exceeds threshold
                    new_val = float(change.new_value)
                    old_val = float(change.old_value) if change.old_value and change.old_value != "?" else new_val
                    if old_val > 0 and new_val / old_val > float(thresh_str):
                        return {"block": f"违反 {category} 策略护栏: {risk}"}
                except (ValueError, ZeroDivisionError):
                    pass
        if "<" in rule:
            key, thresh_str = rule.split("<", 1)
            if key in change.target:
                try:
                    new_val = float(change.new_value)
                    old_val = float(change.old_value) if change.old_value and change.old_value != "?" else new_val
                    if old_val > 0 and new_val / old_val < float(thresh_str):
                        return {"warn": f"触及 {category} 策略警戒线: {risk}"}
                except (ValueError, ZeroDivisionError):
                    pass

    return {}


def _check_duplication(
    change: StrategyChange,
    history: dict,
) -> str | None:
    """Check if the exact same change was attempted before."""
    past_attempts = history.get(change.target, [])
    new_val = change.new_value

    for attempt in past_attempts:
        if str(attempt.get("new_value", "")) == str(new_val):
            success = attempt.get("success", False)
            if not success:
                return (
                    f"相同修改曾在 {attempt.get('timestamp', '?')} 尝试但未成功，"
                    f"建议调整方向或幅度"
                )
            else:
                return f"相同修改曾在 {attempt.get('timestamp', '?')} 成功应用"

    return None


def _check_feasibility(change: StrategyChange) -> str | None:
    """Check if the new value is within feasible bounds."""
    # Extract the leaf key from target path
    leaf_key = change.target.split(".")[-1] if "." in change.target else change.target

    bounds = _FEASIBILITY_BOUNDS.get(leaf_key)
    if bounds is None:
        return None  # No bounds defined for this key → pass

    try:
        new_val = float(change.new_value)
        lo, hi = bounds
        if new_val < lo:
            return f"{change.target}={new_val} 低于可行下限 {lo}"
        if new_val > hi:
            return f"{change.target}={new_val} 超出可行上限 {hi}"
    except (ValueError, TypeError):
        pass

    return None


def _check_multiplier(change: StrategyChange) -> str | None:
    """Check if the change multiplier is too extreme."""
    try:
        new_val = float(change.new_value)
        old_val = float(change.old_value) if change.old_value and change.old_value != "?" else None
    except (ValueError, TypeError):
        return None

    if old_val is None or old_val == 0:
        return None

    ratio = new_val / old_val
    if ratio < 0.5:
        return f"{change.target} 修改幅度 {ratio:.2f}× 过大（减半以上），建议减小幅度"
    if ratio > 2.0:
        return f"{change.target} 修改幅度 {ratio:.2f}× 过大（翻倍以上），建议减小幅度"

    return None
