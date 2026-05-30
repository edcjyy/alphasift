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

    regime: str = "neutral"  # bullish / bearish / neutral / volatile / polarized
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
    snapshot_df: pd.DataFrame | None = None,
) -> MarketState | None:
    """Assess current A-share market state.

    Args:
        index_code: Benchmark index code.
        source: Data source for index history.
        snapshot_df: Optional pre-fetched snapshot with change_pct column.
                     If provided, market breadth is computed from it directly,
                     skipping the efinance fetch.

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
        _assess_breadth(state, snapshot_df=snapshot_df)
    except Exception as exc:
        logger.debug("Breadth assessment failed: %s", exc)

    # 3. Volume regime: total market turnover vs 20-day average
    try:
        _assess_volume_regime(state, index_code, source=source)
    except Exception as exc:
        logger.debug("Volume regime assessment failed: %s", exc)

    # 4. Determine regime and weight adjustments
    _classify_regime(state)

    # 5. Market style detection: growth vs value relative strength
    _detect_market_style(state, snapshot_df=snapshot_df)

    if state.notes:
        logger.info("Market state: regime=%s %s", state.regime, " | ".join(state.notes))

    return state


def _assess_breadth(state: MarketState, *, snapshot_df: pd.DataFrame | None = None) -> None:
    """Compute market breadth from full snapshot (uses snapshot_df if provided)."""
    if snapshot_df is not None and "change_pct" in snapshot_df.columns:
        df = snapshot_df
    else:
        from alphasift.snapshot import fetch_cn_snapshot
        try:
            df = fetch_cn_snapshot(source="efinance")
        except Exception:
            logger.debug("Market breadth: efinance snapshot failed, breadth skipped")
            return

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
    above_ma20 = state.index_vs_ma20_pct > 0.5
    below_ma20 = state.index_vs_ma20_pct < -1.5
    breadth_strong = state.breadth_ratio > 1.0
    breadth_weak = state.breadth_ratio < 0.7
    volume_spike = state.volume_deviation_pct > 30

    if above_ma20 and breadth_strong:
        state.regime = "bullish"
        # Bullish: favor momentum and activity, reduce value weighting
        adjustments["momentum_weight_mult"] = 1.25
        adjustments["activity_weight_mult"] = 1.20
        adjustments["theme_heat_weight_mult"] = 1.15
        adjustments["reversal_weight_mult"] = 0.85
        adjustments["value_weight_mult"] = 0.80
        adjustments["stability_weight_mult"] = 0.85
        state.notes.append("Bullish regime: favoring momentum/activity/theme_heat")
    elif below_ma20 and breadth_weak:
        state.regime = "bearish"
        # Bearish: favor value and stability, reduce momentum
        adjustments["momentum_weight_mult"] = 0.60
        adjustments["activity_weight_mult"] = 0.70
        adjustments["value_weight_mult"] = 1.40
        adjustments["stability_weight_mult"] = 1.30
        adjustments["quality_weight_mult"] = 1.15
        adjustments["reversal_weight_mult"] = 1.10
        adjustments["theme_heat_weight_mult"] = 0.70
        state.notes.append("Bearish regime: favoring value/stability/quality/reversal")
    elif below_ma20 and not breadth_weak:
        # Weakening: index below MA20 but market breadth is still acceptable.
        # This is the transitional state before a full bear market — apply
        # 50%-intensity defensive adjustments to capture the index breakdown
        # signal without over-reacting.
        state.regime = "weakening"
        adjustments["momentum_weight_mult"] = 0.80
        adjustments["activity_weight_mult"] = 0.85
        adjustments["value_weight_mult"] = 1.20
        adjustments["stability_weight_mult"] = 1.15
        adjustments["quality_weight_mult"] = 1.08
        state.notes.append(
            f"Weakening regime (50% bearish): index below MA20 "
            f"({state.index_vs_ma20_pct:+.1f}%) but breadth={state.breadth_ratio:.2f} — "
            "transitional defense, light value/stability tilt"
        )
    elif volume_spike and (not above_ma20):
        state.regime = "volatile"
        # Volatile: tighten risk, favor stability
        adjustments["stability_weight_mult"] = 1.50
        adjustments["momentum_weight_mult"] = 0.70
        adjustments["activity_weight_mult"] = 0.60
        state.notes.append("Volatile regime: favoring stability, reducing speculation")
    elif (
        not above_ma20
        and not below_ma20
        and state.breadth_ratio < 0.50
    ):
        # Polarized: index flat but breadth very weak → extreme divergence
        # Favor theme_heat to capture concentrated leadership, boost quality
        state.regime = "polarized"
        adjustments["theme_heat_weight_mult"] = 1.80
        adjustments["quality_weight_mult"] = 1.30
        adjustments["size_weight_mult"] = 1.25
        adjustments["momentum_weight_mult"] = 0.70
        adjustments["activity_weight_mult"] = 0.65
        adjustments["reversal_weight_mult"] = 0.80
        state.notes.append("Polarized regime: extreme divergence, favoring theme_heat/quality/size")
    else:
        state.regime = "neutral"
        state.notes.append("Neutral regime: no weight adjustment")

    state.weight_adjustments = adjustments


def _detect_market_style(state: MarketState, *, snapshot_df: pd.DataFrame | None = None) -> None:
    """Detect growth vs value market style via index relative strength.

    Compares 20D performance of 创业板指 (growth proxy) vs 上证指数 (value proxy).
    When growth significantly outperforms, boosts momentum/theme_heat and reduces
    value weighting even in neutral regime.
    """
    try:
        gemb_hist = _fetch_index_history("399006.SZ", source="auto")  # 创业板指
        sz_hist = _fetch_index_history("000001.SH", source="auto")     # 上证指数
        if gemb_hist is None or gemb_hist.empty or sz_hist is None or sz_hist.empty:
            return

        gemb_close = pd.to_numeric(gemb_hist["close"], errors="coerce").dropna()
        sz_close = pd.to_numeric(sz_hist["close"], errors="coerce").dropna()
        if len(gemb_close) < 21 or len(sz_close) < 21:
            return

        gemb_20d = (float(gemb_close.iloc[-1]) / float(gemb_close.iloc[-21]) - 1.0) * 100
        sz_20d = (float(sz_close.iloc[-1]) / float(sz_close.iloc[-21]) - 1.0) * 100
        style_spread = round(gemb_20d - sz_20d, 2)

        state.notes.append(f"style_spread={style_spread:.1f}% (GEM={gemb_20d:.1f}% vs SH={sz_20d:.1f}%)")

        # If growth outperforms by >15% in 20D, adjust weights
        if style_spread > 15.0:
            existing = state.weight_adjustments
            existing["momentum_weight_mult"] = existing.get("momentum_weight_mult", 1.0) * 1.20
            existing["theme_heat_weight_mult"] = existing.get("theme_heat_weight_mult", 1.0) * 1.15
            existing["size_weight_mult"] = existing.get("size_weight_mult", 1.0) * 1.10
            existing["value_weight_mult"] = existing.get("value_weight_mult", 1.0) * 0.85
            existing["stability_weight_mult"] = existing.get("stability_weight_mult", 1.0) * 0.90
            state.notes.append(f"Growth-dominant style (spread>{style_spread:.0f}%): boosting momentum/theme_heat/size, reducing value/stability")
        elif style_spread < -15.0:
            # Value outperforms
            existing = state.weight_adjustments
            existing["value_weight_mult"] = existing.get("value_weight_mult", 1.0) * 1.20
            existing["stability_weight_mult"] = existing.get("stability_weight_mult", 1.0) * 1.15
            existing["quality_weight_mult"] = existing.get("quality_weight_mult", 1.0) * 1.10
            existing["momentum_weight_mult"] = existing.get("momentum_weight_mult", 1.0) * 0.85
            state.notes.append(f"Value-dominant style (spread<{style_spread:.0f}%): boosting value/stability/quality, reducing momentum")
    except Exception as exc:
        logger.debug("Market style detection failed: %s", exc)


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
        ("reversal", "reversal_weight_mult"),
        ("activity", "activity_weight_mult"),
        ("stability", "stability_weight_mult"),
        ("size", "size_weight_mult"),
        ("theme_heat", "theme_heat_weight_mult"),
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
