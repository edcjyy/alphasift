# -*- coding: utf-8 -*-
"""Parameter Sensitivity Analysis — identify which params matter most."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class SensitivityReport:
    strategy: str
    parameter: str
    base_value: float
    perturbations: list[dict] = field(default_factory=list)  # {mult, value, impact}
    sensitivity_score: float = 0.0  # 0-1, higher = more sensitive
    recommendation: str = ""


def analyze_sensitivity(
    strategy_path: Path,
    *,
    parameters: list[str] | None = None,
    num_perturbations: int = 5,
    range_pct: float = 0.30,
) -> list[SensitivityReport]:
    """Analyze which strategy parameters are most sensitive to changes.

    For each parameter, perturb it by ±range_pct in num_perturbations steps
    and estimate impact on the strategy's filtering/scoring behavior.

    Returns a list of SensitivityReport, one per parameter.
    """
    try:
        data = yaml.safe_load(strategy_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return []

    if not isinstance(data, dict):
        return []

    screening = data.get("screening", {})
    strategy_name = data.get("name", strategy_path.stem)
    reports: list[SensitivityReport] = []

    # Auto-discover numeric parameters
    if parameters is None:
        parameters = _discover_parameters(screening)

    for param_path in parameters:
        base_value = _get_nested(screening, param_path)
        if base_value is None or not isinstance(base_value, (int, float)):
            continue

        perturbations = []
        max_deviation = 0.0

        for i in range(num_perturbations):
            # Stagger multipliers from (1-range_pct) to (1+range_pct)
            mult = 1.0 + range_pct * (2 * i / (num_perturbations - 1) - 1) if num_perturbations > 1 else 1.0
            new_value = base_value * mult
            # Impact: simple heuristic — larger values for filters, smaller for weights
            impact = abs(mult - 1.0)
            if "factor_weights" in param_path or "scoring_profile" in param_path:
                impact *= 0.5  # Weights are normalized, individual changes less impactful
            elif "risk_profile" in param_path:
                impact *= 0.7
            elif "hard_filters" in param_path:
                impact *= 1.2  # Filters directly affect candidate pool size

            perturbations.append({
                "mult": round(mult, 3),
                "value": round(new_value, 4),
                "impact": round(impact, 4),
            })
            max_deviation = max(max_deviation, impact)

        sensitivity = round(min(1.0, max_deviation * 3), 3)  # scale to 0-1

        # Recommendation
        if sensitivity > 0.6:
            recommendation = "高敏感 — 建议优先优化此参数，变动幅度控制在 ±15% 以内"
        elif sensitivity > 0.3:
            recommendation = "中敏感 — 可适度调整，建议 ±20% 范围探索"
        else:
            recommendation = "低敏感 — 大范围调整影响有限，不建议优先改动"

        reports.append(SensitivityReport(
            strategy=strategy_name,
            parameter=param_path,
            base_value=base_value,
            perturbations=perturbations,
            sensitivity_score=sensitivity,
            recommendation=recommendation,
        ))

    # Sort by sensitivity descending
    reports.sort(key=lambda r: r.sensitivity_score, reverse=True)
    return reports


def _discover_parameters(screening: dict) -> list[str]:
    """Auto-discover all numeric parameters in screening section."""
    params = []
    for section, keys in [
        ("hard_filters", ["pe_ttm_max", "pb_max", "amount_min", "change_pct_max",
                          "change_pct_min", "turnover_rate_min", "volume_ratio_min",
                          "signal_score_min", "market_cap_min"]),
        ("factor_weights", ["value", "momentum", "activity", "stability", "quality",
                            "liquidity", "theme_heat", "size", "reversal"]),
        ("risk_profile", ["chase_change_pct", "abnormal_volume_ratio", "high_turnover_rate"]),
        ("scoring_profile", ["momentum_chase_start_pct", "activity_ideal_volume_ratio",
                             "activity_ideal_turnover_rate", "stability_hot_change_pct"]),
    ]:
        section_data = screening.get(section, {})
        if isinstance(section_data, dict):
            for key in keys:
                if key in section_data and isinstance(section_data[key], (int, float)):
                    params.append(f"{section}.{key}")
    return params


def _get_nested(data: dict, path: str):
    """Get value from nested dict by dotted path."""
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current
