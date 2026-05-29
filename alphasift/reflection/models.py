# -*- coding: utf-8 -*-
"""Reflection Layer — strategy evolution through evaluation-driven analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta


_TZ_SHANGHAI = timezone(timedelta(hours=8))


def _now() -> str:
    return datetime.now(_TZ_SHANGHAI).isoformat()


@dataclass
class StrategyChange:
    """A single proposed parameter change to a strategy YAML."""

    change_type: str  # ADJUST_WEIGHT | MODIFY_FILTER | UPDATE_REGIME | ADD_REGIME | MODIFY_SCORECARD | MODIFY_RISK
    target: str  # e.g. "factor_weights.momentum", "hard_filters.pe_ttm_max"
    old_value: str  # string representation of current value
    new_value: str  # string representation of proposed value
    reason: str  # one-line explanation from LLM
    confidence: float = 0.5  # 0.0-1.0 from LLM


@dataclass
class ReflectionResult:
    """Complete output from one reflection analysis."""

    run_id: str
    strategy: str
    evaluated_at: str
    reflected_at: str = field(default_factory=_now)
    diagnosis: str = ""  # full LLM diagnosis text
    changes: list[StrategyChange] = field(default_factory=list)
    summary: str = ""  # condensed summary for display
    # Evaluation context
    win_rate: float | None = None
    avg_return_pct: float | None = None
    elapsed_days: int | None = None
    pick_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    # Metadata
    model_used: str = ""
    raw_response: str = ""  # raw LLM response for debugging
