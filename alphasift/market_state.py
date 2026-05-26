# -*- coding: utf-8 -*-
"""Market state awareness module.

Computes lightweight market environment indicators to inform strategy
weight adjustments: breadth, trend, and volume regimes.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class MarketState:
    """Snapshot of current market environment."""

    regime: str = "neutral"  # bullish / bearish / neutral / volatile
    breadth_ratio: float = 0.0  # advancers / decliners
    index_vs_ma20_pct: float = 0.0  # HS300 close vs 20-day MA
    volume_deviation_pct: float = 0.0  # turnover vs 20-day average
    vix_estimate: float | None = None  # crude volatility proxy
    weight_adjustments: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def assess_market_state(
    *,
    index_code: str = "000300.SH",
    source: str = "auto",
) -> MarketState | None:
    """Assess current A-share market state.

    Returns None if data sources are unavailable.
    """
    state = MarketState()

    # 1. Index trend: HS300 close vs 20-day MA
    try:
        hist = _fetch_index_history(index_code, source=source)
        if hist is not None and not hist.empty:
            close = pd.to_numeric(hist["close"], errors="coerce").dropna()
            if len(close) >= 20:
                ma20 = close.rolling(20).mean()
                last_close = float(close.iloc[-1])
                last_ma20 = float(ma20.iloc[-1])
                if last_ma20 > 0:
                    state.index_vs_ma20_pct = round((last_close / last_ma20 - 1.0) * 100, 2)

                # 20-day trend
                if len(close) >= 21:
                    close_20d_ago = float(close.iloc[-21])
                    if close_20d_ago > 0:
                        index_trend_20d = (last_close / close_20d_ago - 1.0) * 100
                        state.notes.append(f"HS300 20d trend={index_trend_20d:.1f}%")
    except Exception as exc:
        logger.debug("Index history fetch failed: %s", exc)

    # 2. Market breadth: advance/decline ratio from snapshot
    try:
        _assess_breadth(state)
    except Exception as exc:
        logger.debug("Breadth assessment failed: %s", exc)

    # 3. Volume regime: total market turnover vs 20-day average
    try:
        _assess_volume_regime(state, index_code, source=source)
    except Exception as exc:
        logger.debug("Volume regime assessment failed: %s", exc)

    # 4. Determine regime and weight adjustments
    _classify_regime(state)

    if state.notes:
        logger.info("Market state: regime=%s %s", state.regime, " | ".join(state.notes))

    return state


def _assess_breadth(state: MarketState) -> None:
    """Compute market breadth from full snapshot."""
    from alphasift.snapshot import fetch_cn_snapshot

    df = fetch_cn_snapshot(source="efinance")
    if df is None or df.empty or "change_pct" not in df.columns:
        return

    change = pd.to_numeric(df["change_pct"], errors="coerce").dropna()
    if change.empty:
        return

    advancers = (change > 0).sum()
    decliners = (change < 0).sum()
    total = advancers + decliners
    if total > 0 and decliners > 0:
        state.breadth_ratio = round(advancers / decliners, 2)
    elif decliners == 0 and advancers > 0:
        state.breadth_ratio = 10.0  # extreme bullish
    state.notes.append(f"breadth={state.breadth_ratio:.2f} (adv={advancers} dec={decliners})")


def _assess_volume_regime(state: MarketState, index_code: str, *, source: str = "auto") -> None:
    """Assess whether current volume is above/below normal."""
    hist = _fetch_index_history(index_code, source=source)
    if hist is None or hist.empty or "volume" not in hist.columns:
        return

    volume = pd.to_numeric(hist["volume"], errors="coerce").dropna()
    if len(volume) < 20:
        return

    avg_vol_20d = float(volume.iloc[-21:-1].mean())
    today_vol = float(volume.iloc[-1])
    if avg_vol_20d > 0:
        state.volume_deviation_pct = round((today_vol / avg_vol_20d - 1.0) * 100, 2)
        state.notes.append(f"volume_dev={state.volume_deviation_pct:.1f}%")


def _classify_regime(state: MarketState) -> None:
    """Classify market into 4 regimes and compute weight adjustments."""
    adjustments: dict[str, float] = {}

    # Determine regime
    above_ma20 = state.index_vs_ma20_pct > 1.0
    below_ma20 = state.index_vs_ma20_pct < -2.0
    breadth_strong = state.breadth_ratio > 1.3
    breadth_weak = state.breadth_ratio < 0.6
    volume_spike = state.volume_deviation_pct > 30

    if above_ma20 and breadth_strong:
        state.regime = "bullish"
        # Bullish: favor momentum and activity, reduce value weighting
        adjustments["momentum_weight_mult"] = 1.25
        adjustments["activity_weight_mult"] = 1.20
        adjustments["value_weight_mult"] = 0.80
        adjustments["stability_weight_mult"] = 0.85
        state.notes.append("Bullish regime: favoring momentum/activity")
    elif below_ma20 and breadth_weak:
        state.regime = "bearish"
        # Bearish: favor value and stability, reduce momentum
        adjustments["momentum_weight_mult"] = 0.60
        adjustments["activity_weight_mult"] = 0.70
        adjustments["value_weight_mult"] = 1.40
        adjustments["stability_weight_mult"] = 1.30
        adjustments["quality_weight_mult"] = 1.15
        state.notes.append("Bearish regime: favoring value/stability/quality")
    elif volume_spike and (not above_ma20):
        state.regime = "volatile"
        # Volatile: tighten risk, favor stability
        adjustments["stability_weight_mult"] = 1.50
        adjustments["momentum_weight_mult"] = 0.70
        adjustments["activity_weight_mult"] = 0.60
        state.notes.append("Volatile regime: favoring stability, reducing speculation")
    else:
        state.regime = "neutral"
        state.notes.append("Neutral regime: no weight adjustment")

    state.weight_adjustments = adjustments


def _fetch_index_history(code: str, *, source: str = "auto") -> pd.DataFrame | None:
    """Fetch index K-line history. Tries Tushare then akshare."""
    if source in ("auto", "tushare"):
        token = os.getenv("TUSHARE_TOKEN", "").strip() or os.getenv("TUSHARE_API_TOKEN", "").strip()
        if token:
            try:
                import tushare as ts

                pro = ts.pro_api(token)
                proxy_url = os.getenv("TUSHARE_API_URL", "").strip()
                if proxy_url:
                    pro._DataApi__token = token
                    pro._DataApi__http_url = proxy_url

                end_date = datetime.now().strftime("%Y%m%d")
                start_date = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")
                df = pro.index_daily(
                    ts_code=code,
                    start_date=start_date,
                    end_date=end_date,
                    fields="trade_date,close,vol",
                )
                if df is not None and not df.empty:
                    df = df.rename(columns={"trade_date": "date", "vol": "volume"})
                    df = df.sort_values("date").reset_index(drop=True)
                    return df
            except Exception as exc:
                logger.debug("Tushare index fetch failed: %s", exc)

    if source in ("auto", "akshare"):
        try:
            import akshare as ak

            df = ak.stock_zh_index_daily(symbol=f"sh{code.split('.')[0]}")
            if df is not None and not df.empty:
                df = df.rename(columns={"date": "date", "close": "close", "volume": "volume"})
                return df.tail(30)
        except Exception as exc:
            logger.debug("akshare index fetch failed: %s", exc)

    return None


def apply_market_state_weights(
    weights: dict[str, float],
    state: MarketState | None,
) -> dict[str, float]:
    """Apply market state adjustments to factor weights.

    Returns a new dict with adjusted weights, re-normalized to sum to 1.0.
    """
    if state is None or state.regime == "neutral":
        return dict(weights)

    adjusted = dict(weights)
    for factor, mult_key in [
        ("value", "value_weight_mult"),
        ("momentum", "momentum_weight_mult"),
        ("activity", "activity_weight_mult"),
        ("stability", "stability_weight_mult"),
        ("quality", "quality_weight_mult"),
    ]:
        mult = state.weight_adjustments.get(mult_key, 1.0)
        if factor in adjusted:
            adjusted[factor] *= mult

    # Re-normalize
    total = sum(adjusted.values())
    if total > 0:
        adjusted = {k: v / total for k, v in adjusted.items()}

    return adjusted
