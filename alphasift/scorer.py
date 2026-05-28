# -*- coding: utf-8 -*-
"""screen_score calculation."""

import pandas as pd

from alphasift.models import ScreeningConfig

_FACTOR_COLUMNS = {
    "value": "factor_value_score",
    "liquidity": "factor_liquidity_score",
    "momentum": "factor_momentum_score",
    "reversal": "factor_reversal_score",
    "activity": "factor_activity_score",
    "stability": "factor_stability_score",
    "size": "factor_size_score",
    "theme_heat": "factor_theme_heat_score",
    "quality": "factor_quality_score",
}
_DEFAULT_SCORING_PROFILE = {
    "momentum_base": 60.0,
    "momentum_intraday_slope": 5.0,
    "momentum_chase_start_pct": 5.0,
    "momentum_chase_penalty_slope": 10.0,
    "momentum_downside_start_pct": -2.0,
    "momentum_downside_penalty_slope": 3.0,
    "momentum_60d_base": 55.0,
    "momentum_60d_slope": 0.9,
    "momentum_60d_overheat_pct": 55.0,
    "momentum_60d_overheat_penalty_slope": 0.8,
    "momentum_60d_breakdown_pct": -20.0,
    "momentum_60d_breakdown_penalty_slope": 0.7,
    "macd_bullish_bonus": 6.0,
    "macd_bearish_penalty": 8.0,
    "momentum_5d_slope": 4.0,
    "momentum_5d_overheat_pct": 15.0,
    "momentum_5d_overheat_penalty_slope": 3.0,
    "momentum_5d_breakdown_pct": -5.0,
    "momentum_5d_breakdown_penalty_slope": 2.5,
    "momentum_20d_base": 52.0,
    "momentum_20d_slope": 1.5,
    "momentum_20d_overheat_pct": 30.0,
    "momentum_20d_overheat_penalty_slope": 1.0,
    "momentum_20d_breakdown_pct": -12.0,
    "momentum_20d_breakdown_penalty_slope": 1.0,
    "momentum_120d_base": 50.0,
    "momentum_120d_slope": 0.4,
    "momentum_120d_overheat_pct": 80.0,
    "momentum_120d_overheat_penalty_slope": 0.5,
    "momentum_120d_breakdown_pct": -25.0,
    "momentum_120d_breakdown_penalty_slope": 0.5,
    "momentum_sector_neutral": False,
    "value_sector_neutral": False,
    "quality_roe_ideal": 15.0,
    "quality_roe_distance_slope": 4.0,
    "quality_roe_negative_penalty": 25.0,
    # Factor interaction: GARP (growth at reasonable price) bonus
    "garp_value_threshold": 55.0,
    "garp_momentum_threshold": 55.0,
    "garp_bonus": 6.0,
    # Factor interaction: hollow rally penalty (momentum w/o volume)
    "hollow_momentum_threshold": 60.0,
    "hollow_volume_max": 1.2,
    "hollow_penalty": 5.0,
    # Factor interaction: hot money penalty (high activity, low stability)
    "hot_money_activity_threshold": 60.0,
    "hot_money_stability_threshold": 45.0,
    "hot_money_interact_penalty": 5.0,
    "reversal_ideal_change_pct": -3.0,
    "reversal_distance_penalty_slope": 13.0,
    "reversal_collapse_start_pct": -8.0,
    "reversal_collapse_penalty_slope": 10.0,
    "reversal_chase_start_pct": 1.0,
    "reversal_chase_penalty_slope": 8.0,
    "rsi_oversold_bonus": 10.0,
    "rsi_overbought_penalty": 14.0,
    "activity_ideal_volume_ratio": 2.0,
    "activity_volume_ratio_distance_slope": 15.0,
    "activity_high_volume_ratio": 5.0,
    "activity_high_volume_ratio_penalty_slope": 8.0,
    "activity_ideal_turnover_rate": 4.0,
    "activity_turnover_distance_slope": 8.0,
    "activity_high_turnover_rate": 12.0,
    "activity_high_turnover_penalty_slope": 5.0,
    "stability_base": 78.0,
    "stability_change_abs_penalty_slope": 3.0,
    "stability_hot_change_pct": 7.0,
    "stability_hot_change_penalty_slope": 5.0,
    "stability_high_turnover_rate": 10.0,
    "stability_high_turnover_penalty_slope": 2.0,
    "stability_high_volume_ratio": 5.0,
    "stability_high_volume_ratio_penalty_slope": 4.0,
    "stability_invalid_pe_penalty": 12.0,
    "theme_heat_unknown_score": 50.0,
    "theme_heat_change_slope": 6.0,
    "theme_heat_rank_bonus": 10.0,
    "theme_heat_trend_min_observations": 2.0,
    "theme_heat_trend_slope": 0.8,
    "theme_heat_trend_bonus_cap": 10.0,
    "theme_heat_cooling_penalty_slope": 0.8,
    "theme_heat_cooling_penalty_cap": 12.0,
    "theme_heat_persistence_min_score": 60.0,
    "theme_heat_persistence_slope": 0.08,
    "theme_heat_persistence_bonus_cap": 6.0,
    "theme_heat_cooling_score_penalty_slope": 0.6,
    "theme_heat_cooling_score_penalty_cap": 10.0,
    "theme_heat_overheat_score": 88.0,
    "theme_heat_overheat_penalty_slope": 0.5,
}


def compute_screen_scores(
    df: pd.DataFrame,
    config: ScreeningConfig,
    *,
    market_state_weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Compute screen_score for each candidate row.

    Adds a 'screen_score' column (0-100). Higher is better.
    Supports sector-neutral scoring, quality factor, factor interactions,
    and market-state-driven weight adjustments.
    """
    result = df.copy()
    factors = _compute_factor_scores(result, config)
    for name, series in factors.items():
        col_name = _FACTOR_COLUMNS.get(name)
        if col_name:
            result[col_name] = series.round(4)

    weights = market_state_weights if market_state_weights else _normalized_factor_weights(config)
    result["screen_score"] = 0.0
    for factor, weight in weights.items():
        if factor in factors:
            result["screen_score"] += factors[factor] * weight

    # Factor interaction effects (non-linear bonuses/penalties)
    profile = _scoring_profile(config)
    result["screen_score"] += _compute_interaction_effects(result, factors, profile)

    result["screen_score"] = result["screen_score"].clip(0, 100)

    return result


def factor_score_columns() -> dict[str, str]:
    """Return the stable factor-score column mapping used in Pick output."""
    return dict(_FACTOR_COLUMNS)


def _normalized_factor_weights(config: ScreeningConfig) -> dict[str, float]:
    """Use explicit factor weights, or derive a sane legacy default from tech_weight."""
    tw = config.tech_weight
    raw_weights = config.factor_weights or {
        # Fundamental cluster (weight = 1 - tech_weight)
        "value": (1 - tw) * 0.35,
        "liquidity": (1 - tw) * 0.15,
        "stability": (1 - tw) * 0.15,
        "quality": (1 - tw) * 0.15,
        "size": (1 - tw) * 0.10,
        # Technical cluster (weight = tech_weight)
        "momentum": tw * 0.40,
        "activity": tw * 0.35,
        # Cross-cluster factors (split between clusters)
        "reversal": 0.04,
        "theme_heat": 0.06,
    }
    weights = {
        factor: max(float(weight), 0.0)
        for factor, weight in raw_weights.items()
        if factor in _FACTOR_COLUMNS
    }
    total = sum(weights.values())
    if total <= 0:
        return {
            "value": 0.30, "liquidity": 0.15, "momentum": 0.20,
            "activity": 0.15, "quality": 0.10, "stability": 0.10,
        }
    return {factor: weight / total for factor, weight in weights.items()}


def _compute_factor_scores(df: pd.DataFrame, config: ScreeningConfig | None = None) -> dict[str, pd.Series]:
    config = config or ScreeningConfig()
    profile = _scoring_profile(config)
    return {
        "value": _compute_value_score(df, profile),
        "liquidity": _compute_liquidity_score(df),
        "momentum": _compute_momentum_score(df, profile),
        "reversal": _compute_reversal_score(df, profile),
        "activity": _compute_activity_score(df, profile),
        "stability": _compute_stability_score(df, profile),
        "size": _compute_size_score(df),
        "theme_heat": _compute_theme_heat_score(df, profile),
        "quality": _compute_quality_score(df, profile),
    }


def _scoring_profile(config: ScreeningConfig) -> dict[str, float]:
    profile = dict(_DEFAULT_SCORING_PROFILE)
    for key, value in (config.scoring_profile or {}).items():
        if key in profile:
            profile[key] = float(value)
    return profile


def _compute_snapshot_score(df: pd.DataFrame) -> pd.Series:
    """Score based on snapshot fundamentals (0-100).

    Components:
    - PE ratio: lower is better (for value), normalized
    - PB ratio: lower is better, normalized
    - Turnover rate: moderate is best
    - Amount (liquidity): higher is better, log-scaled
    - Change pct: near zero or moderate positive preferred
    """
    factors = _compute_factor_scores(df)
    return (
        factors["value"] * 0.50
        + factors["liquidity"] * 0.25
        + factors["stability"] * 0.25
    ).clip(0, 100)


def _compute_tech_score(df: pd.DataFrame) -> pd.Series:
    """Score based on technical features (0-100).

    Uses available columns like volume_ratio, change_pct patterns.
    Full tech scoring (MA structure, MACD/RSI) needs daily data,
    which is not in the snapshot — scored conservatively here.
    """
    factors = _compute_factor_scores(df)
    return (factors["momentum"] * 0.55 + factors["activity"] * 0.45).clip(0, 100)


def _compute_value_score(df: pd.DataFrame, profile: dict[str, float] | None = None) -> pd.Series:
    profile = profile or {}
    sector_neutral = bool(profile.get("value_sector_neutral", False))
    score = pd.Series(50.0, index=df.index)

    if "pe_ratio" in df.columns:
        pe = pd.to_numeric(df["pe_ratio"], errors="coerce")
        pe_score = _rank_score(
            pe.where((pe > 0) & (pe < 500)),
            lower_is_better=True,
            na_score=25,
            sector_series=df.get("industry") if sector_neutral else None,
        )
        score = score * 0.35 + pe_score * 0.65

    if "pb_ratio" in df.columns:
        pb = pd.to_numeric(df["pb_ratio"], errors="coerce")
        pb_score = _rank_score(
            pb.where((pb > 0) & (pb < 50)),
            lower_is_better=True,
            na_score=25,
            sector_series=df.get("industry") if sector_neutral else None,
        )
        score = score * 0.55 + pb_score * 0.45

    return score.clip(0, 100)


def _compute_liquidity_score(df: pd.DataFrame) -> pd.Series:
    if "amount" not in df.columns:
        return pd.Series(50.0, index=df.index)

    import numpy as np

    amount = pd.to_numeric(df["amount"], errors="coerce")
    log_amount = np.log10(amount.clip(lower=1))
    return _rank_score(log_amount.where(amount > 0), lower_is_better=False, na_score=20)


def _compute_momentum_score(df: pd.DataFrame, profile: dict[str, float]) -> pd.Series:
    score = pd.Series(50.0, index=df.index)

    if "change_pct" in df.columns:
        change = pd.to_numeric(df["change_pct"], errors="coerce").fillna(0)
        # Prefer constructive positive moves, but penalize chase-risk near limit-up.
        intraday_score = profile["momentum_base"] + change * profile["momentum_intraday_slope"]
        intraday_score = intraday_score - (
            change - profile["momentum_chase_start_pct"]
        ).clip(lower=0) * profile["momentum_chase_penalty_slope"]
        intraday_score = intraday_score - (
            -change + profile["momentum_downside_start_pct"]
        ).clip(lower=0) * profile["momentum_downside_penalty_slope"]
        score = score * 0.25 + intraday_score.clip(5, 100) * 0.75

    # 5-day momentum (short-term trend — key for trend-following strategies)
    if "change_5d" in df.columns:
        change_5d = pd.to_numeric(df["change_5d"], errors="coerce").fillna(0)
        trend_5d_score = 50.0 + change_5d * profile.get("momentum_5d_slope", 4.0)
        trend_5d_score = trend_5d_score - (
            change_5d - profile.get("momentum_5d_overheat_pct", 15.0)
        ).clip(lower=0) * profile.get("momentum_5d_overheat_penalty_slope", 3.0)
        trend_5d_score = trend_5d_score - (
            -change_5d + profile.get("momentum_5d_breakdown_pct", -5.0)
        ).clip(lower=0) * profile.get("momentum_5d_breakdown_penalty_slope", 2.5)
        score = score * 0.75 + trend_5d_score.clip(5, 100) * 0.25

    # 20-day momentum (medium-term trend — bridges daily and monthly)
    if "change_20d" in df.columns:
        change_20d = pd.to_numeric(df["change_20d"], errors="coerce").fillna(0)
        base_20d = profile.get("momentum_20d_base", 52.0)
        trend_20d_score = base_20d + change_20d * profile.get("momentum_20d_slope", 1.5)
        trend_20d_score = trend_20d_score - (
            change_20d - profile.get("momentum_20d_overheat_pct", 30.0)
        ).clip(lower=0) * profile.get("momentum_20d_overheat_penalty_slope", 1.0)
        trend_20d_score = trend_20d_score - (
            -change_20d + profile.get("momentum_20d_breakdown_pct", -12.0)
        ).clip(lower=0) * profile.get("momentum_20d_breakdown_penalty_slope", 1.0)
        score = score * 0.75 + trend_20d_score.clip(5, 100) * 0.25

    # 60-day momentum (retain original behavior for compatibility)
    if "change_60d" in df.columns:
        change_60d = pd.to_numeric(df["change_60d"], errors="coerce").fillna(0)
        trend_score = profile["momentum_60d_base"] + change_60d * profile["momentum_60d_slope"]
        trend_score = trend_score - (
            change_60d - profile["momentum_60d_overheat_pct"]
        ).clip(lower=0) * profile["momentum_60d_overheat_penalty_slope"]
        trend_score = trend_score - (
            -change_60d + profile["momentum_60d_breakdown_pct"]
        ).clip(lower=0) * profile["momentum_60d_breakdown_penalty_slope"]
        score = score * 0.75 + trend_score.clip(5, 100) * 0.25

    # 120-day momentum (long-term trend — backdrop context)
    if "change_120d" in df.columns:
        change_120d = pd.to_numeric(df["change_120d"], errors="coerce").fillna(0)
        base_120d = profile.get("momentum_120d_base", 50.0)
        trend_120d_score = base_120d + change_120d * profile.get("momentum_120d_slope", 0.4)
        trend_120d_score = trend_120d_score - (
            change_120d - profile.get("momentum_120d_overheat_pct", 80.0)
        ).clip(lower=0) * profile.get("momentum_120d_overheat_penalty_slope", 0.5)
        trend_120d_score = trend_120d_score - (
            -change_120d + profile.get("momentum_120d_breakdown_pct", -25.0)
        ).clip(lower=0) * profile.get("momentum_120d_breakdown_penalty_slope", 0.5)
        score = score * 0.85 + trend_120d_score.clip(5, 100) * 0.15

    if "signal_score" in df.columns:
        signal = pd.to_numeric(df["signal_score"], errors="coerce").fillna(50)
        score = score * 0.70 + signal.clip(0, 100) * 0.30

    if "macd_status" in df.columns:
        macd = df["macd_status"].astype(str)
        score = score + macd.map({
            "bullish": profile["macd_bullish_bonus"],
            "bearish": -profile["macd_bearish_penalty"],
        }).fillna(0)

    return score.clip(5, 100)


def _compute_reversal_score(df: pd.DataFrame, profile: dict[str, float]) -> pd.Series:
    if "change_pct" not in df.columns:
        return pd.Series(50.0, index=df.index)

    change = pd.to_numeric(df["change_pct"], errors="coerce").fillna(0)
    # Reversal setups prefer controlled weakness, not collapse.
    score = 100 - (
        change - profile["reversal_ideal_change_pct"]
    ).abs() * profile["reversal_distance_penalty_slope"]
    score = score - (
        -change + profile["reversal_collapse_start_pct"]
    ).clip(lower=0) * profile["reversal_collapse_penalty_slope"]
    score = score - (
        change - profile["reversal_chase_start_pct"]
    ).clip(lower=0) * profile["reversal_chase_penalty_slope"]

    if "rsi_status" in df.columns:
        rsi = df["rsi_status"].astype(str)
        score = score + rsi.map({
            "oversold": profile["rsi_oversold_bonus"],
            "overbought": -profile["rsi_overbought_penalty"],
        }).fillna(0)
    if "change_60d" in df.columns:
        change_60d = pd.to_numeric(df["change_60d"], errors="coerce").fillna(0)
        score = score - (change_60d - 35).clip(lower=0) * 0.5
        score = score - (-change_60d - 35).clip(lower=0) * 0.8
    return score.clip(5, 100)


def _compute_activity_score(df: pd.DataFrame, profile: dict[str, float]) -> pd.Series:
    score = pd.Series(50.0, index=df.index)

    if "volume_ratio" in df.columns:
        volume_ratio = pd.to_numeric(df["volume_ratio"], errors="coerce").fillna(1.0)
        vr_score = 100 - (
            volume_ratio - profile["activity_ideal_volume_ratio"]
        ).abs() * profile["activity_volume_ratio_distance_slope"]
        vr_score = vr_score - (
            volume_ratio - profile["activity_high_volume_ratio"]
        ).clip(lower=0) * profile["activity_high_volume_ratio_penalty_slope"]
        score = score * 0.45 + vr_score.clip(5, 100) * 0.55

    if "turnover_rate" in df.columns:
        turnover = pd.to_numeric(df["turnover_rate"], errors="coerce").fillna(0)
        turnover_score = 100 - (
            turnover - profile["activity_ideal_turnover_rate"]
        ).abs() * profile["activity_turnover_distance_slope"]
        turnover_score = turnover_score - (
            turnover - profile["activity_high_turnover_rate"]
        ).clip(lower=0) * profile["activity_high_turnover_penalty_slope"]
        turnover_score = turnover_score.where(turnover > 0, 40)
        score = score * 0.55 + turnover_score.clip(5, 100) * 0.45

    return score.clip(0, 100)


def _compute_stability_score(df: pd.DataFrame, profile: dict[str, float]) -> pd.Series:
    score = pd.Series(profile["stability_base"], index=df.index)

    if "change_pct" in df.columns:
        change = pd.to_numeric(df["change_pct"], errors="coerce").fillna(0)
        score -= change.abs().clip(upper=10) * profile["stability_change_abs_penalty_slope"]
        score -= (
            change - profile["stability_hot_change_pct"]
        ).clip(lower=0) * profile["stability_hot_change_penalty_slope"]

    if "turnover_rate" in df.columns:
        turnover = pd.to_numeric(df["turnover_rate"], errors="coerce").fillna(0)
        score -= (
            turnover - profile["stability_high_turnover_rate"]
        ).clip(lower=0) * profile["stability_high_turnover_penalty_slope"]

    if "volume_ratio" in df.columns:
        volume_ratio = pd.to_numeric(df["volume_ratio"], errors="coerce").fillna(1)
        score -= (
            volume_ratio - profile["stability_high_volume_ratio"]
        ).clip(lower=0) * profile["stability_high_volume_ratio_penalty_slope"]

    if "pe_ratio" in df.columns:
        pe = pd.to_numeric(df["pe_ratio"], errors="coerce")
        score = score.where((pe.isna()) | (pe > 0), score - profile["stability_invalid_pe_penalty"])

    if "signal_score" in df.columns:
        signal = pd.to_numeric(df["signal_score"], errors="coerce").fillna(50)
        score = score + (signal - 50) * 0.12

    return score.clip(0, 100)


def _compute_size_score(df: pd.DataFrame) -> pd.Series:
    if "total_mv" not in df.columns:
        return pd.Series(50.0, index=df.index)

    import numpy as np

    mv = pd.to_numeric(df["total_mv"], errors="coerce")
    log_mv = np.log10(mv.clip(lower=1))
    return _rank_score(log_mv.where(mv > 0), lower_is_better=False, na_score=35)


def _compute_theme_heat_score(df: pd.DataFrame, profile: dict[str, float]) -> pd.Series:
    base = pd.Series(profile["theme_heat_unknown_score"], index=df.index)
    if "board_heat_score" in df.columns:
        score = pd.to_numeric(df["board_heat_score"], errors="coerce").fillna(base)
    elif "industry_heat_score" in df.columns or "concept_heat_score" in df.columns:
        industry = _numeric_column(df, "industry_heat_score")
        concept = _numeric_column(df, "concept_heat_score")
        score = pd.concat([industry, concept], axis=1).max(axis=1).fillna(base)
    elif "industry_change_pct" in df.columns:
        change = pd.to_numeric(df["industry_change_pct"], errors="coerce").fillna(0)
        score = base + change * profile["theme_heat_change_slope"]
        if "industry_rank" in df.columns:
            rank = pd.to_numeric(df["industry_rank"], errors="coerce")
            score += (
                (profile["theme_heat_rank_bonus"] - rank.clip(lower=1, upper=10))
                .clip(lower=0)
                .fillna(0)
            )
    else:
        return base.clip(0, 100)

    if "board_heat_trend_score" in df.columns:
        trend = pd.to_numeric(df["board_heat_trend_score"], errors="coerce").fillna(0)
        if "board_heat_observations" in df.columns:
            observations = pd.to_numeric(df["board_heat_observations"], errors="coerce").fillna(0)
        else:
            observations = pd.Series(profile["theme_heat_trend_min_observations"], index=df.index)
        trend_is_reliable = observations >= profile["theme_heat_trend_min_observations"]
        trend_bonus = (trend.clip(lower=0) * profile["theme_heat_trend_slope"]).clip(
            upper=profile["theme_heat_trend_bonus_cap"]
        )
        cooling_penalty = ((-trend).clip(lower=0) * profile["theme_heat_cooling_penalty_slope"]).clip(
            upper=profile["theme_heat_cooling_penalty_cap"]
        )
        score = score + (trend_bonus - cooling_penalty).where(trend_is_reliable, 0)

    if "board_heat_persistence_score" in df.columns:
        persistence = pd.to_numeric(df["board_heat_persistence_score"], errors="coerce").fillna(0)
        persistence_bonus = (
            (persistence - profile["theme_heat_persistence_min_score"]).clip(lower=0)
            * profile["theme_heat_persistence_slope"]
        ).clip(upper=profile["theme_heat_persistence_bonus_cap"])
        score = score + persistence_bonus

    if "board_heat_cooling_score" in df.columns:
        cooling = pd.to_numeric(df["board_heat_cooling_score"], errors="coerce").fillna(0)
        cooling_penalty = (cooling * profile["theme_heat_cooling_score_penalty_slope"]).clip(
            upper=profile["theme_heat_cooling_score_penalty_cap"]
        )
        score = score - cooling_penalty

    overheat = (score - profile["theme_heat_overheat_score"]).clip(lower=0)
    score = score - overheat * profile["theme_heat_overheat_penalty_slope"]
    return score.clip(0, 100)


def _numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(pd.NA, index=df.index)
    return pd.to_numeric(df[column], errors="coerce")


def _rank_score(
    series: pd.Series,
    *,
    lower_is_better: bool,
    na_score: float = 50.0,
    sector_series: pd.Series | None = None,
) -> pd.Series:
    """Percentile-rank a numeric series to 0-100.

    When ``sector_series`` is provided, ranks are computed within each sector
    (industry group) first, then merged back. This avoids sector bias (e.g.,
    all bank stocks dominating low-PE rankings).
    """
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() == 0:
        return pd.Series(float(na_score), index=series.index)

    if sector_series is not None:
        sectors = sector_series.fillna("__unknown__").astype(str)
        sector_dfs = []
        for sector in sectors.unique():
            mask = sectors == sector
            sector_values = numeric[mask]
            if sector_values.notna().sum() == 0:
                sector_ranks = pd.Series(float(na_score), index=sector_values.index)
            elif sector_values.notna().sum() == 1:
                # Single stock in sector → assign median score
                sector_ranks = pd.Series(55.0, index=sector_values.index)
            else:
                sector_ranks = sector_values.rank(
                    ascending=not lower_is_better,
                    na_option="keep",
                    pct=True,
                ) * 100
            sector_dfs.append(sector_ranks.fillna(float(na_score)))
        if sector_dfs:
            ranks = pd.concat(sector_dfs).reindex(series.index)
        else:
            ranks = pd.Series(float(na_score), index=series.index)
    else:
        ranks = numeric.rank(
            ascending=not lower_is_better,
            na_option="keep",
            pct=True,
        ) * 100

    return ranks.fillna(float(na_score)).clip(0, 100)


# ---- Factor 9: Quality (fundamentals) ----


def _compute_quality_score(df: pd.DataFrame, profile: dict[str, float]) -> pd.Series:
    """Score based on fundamental quality — ROE as the primary anchor.

    Falls back gracefully when ROE data is unavailable:
      - ROE available → center around ideal ROE (default 15%)
      - ROE missing → 50 neutral score, does NOT penalize
    """
    score = pd.Series(50.0, index=df.index)
    if "roe" not in df.columns:
        return score

    roe = pd.to_numeric(df["roe"], errors="coerce")
    ideal = profile.get("quality_roe_ideal", 15.0)

    # Score drops with distance from ideal ROE
    roe_score = 100.0 - (roe - ideal).abs() * profile.get("quality_roe_distance_slope", 4.0)
    # Heavy penalty for negative ROE
    roe_score = roe_score - (-roe.clip(upper=0)).abs() * profile.get("quality_roe_negative_penalty", 25.0)
    # For stocks with valid ROE, override base; for missing, keep neutral 50
    score = roe_score.clip(5, 100).where(roe.notna(), 50.0)

    return score


# ---- Factor Interactions ----


def _compute_interaction_effects(
    _df: pd.DataFrame,
    factors: dict[str, pd.Series],
    profile: dict[str, float],
) -> pd.Series:
    """Compute non-linear factor interaction bonuses/penalties.

    Returns a Series of score adjustments (positive or negative) per candidate.
    """
    result = pd.Series(0.0, index=factors.get("value", pd.Series()).index)

    value = factors.get("value", pd.Series(50.0, index=result.index))
    momentum = factors.get("momentum", pd.Series(50.0, index=result.index))
    activity = factors.get("activity", pd.Series(50.0, index=result.index))
    stability = factors.get("stability", pd.Series(50.0, index=result.index))

    # GARP bonus: value + momentum both above threshold → growth at reasonable price
    garp_value_threshold = profile.get("garp_value_threshold", 55.0)
    garp_momentum_threshold = profile.get("garp_momentum_threshold", 55.0)
    garp_bonus = profile.get("garp_bonus", 6.0)
    garp_mask = (value >= garp_value_threshold) & (momentum >= garp_momentum_threshold)
    result = result + garp_mask.astype(float) * garp_bonus

    # Hollow rally penalty: momentum high but liquidity/volume low → potentially unreliable
    if "volume_ratio" in _df.columns:
        volume_ratio = pd.to_numeric(_df["volume_ratio"], errors="coerce").fillna(1.0)
    else:
        volume_ratio = pd.Series(1.0, index=result.index)

    hollow_momentum_threshold = profile.get("hollow_momentum_threshold", 60.0)
    hollow_volume_max = profile.get("hollow_volume_max", 1.2)
    hollow_penalty = profile.get("hollow_penalty", 5.0)
    hollow_mask = (momentum >= hollow_momentum_threshold) & (volume_ratio <= hollow_volume_max)
    result = result - hollow_mask.astype(float) * hollow_penalty

    # Hot money penalty: high activity + low stability → speculative chase
    hot_activity_threshold = profile.get("hot_money_activity_threshold", 60.0)
    hot_stability_threshold = profile.get("hot_money_stability_threshold", 45.0)
    hot_penalty = profile.get("hot_money_interact_penalty", 5.0)
    hot_mask = (activity >= hot_activity_threshold) & (stability <= hot_stability_threshold)
    result = result - hot_mask.astype(float) * hot_penalty

    return result
