# -*- coding: utf-8 -*-
"""Fundamental financial data enrichment.

Fetches key quality metrics (primarily ROE) for candidate stocks.
Uses Tushare fina_indicator as primary source with automatic fallback
to daily_basic-based estimation when the token lacks sufficient credits.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_ROE_FALLBACK_VALUES = {
    "roe": np.nan,
    "roe_source": "",
}


def enrich_roe(
    df: pd.DataFrame,
    *,
    force_tushare_fallback: bool = False,
) -> pd.DataFrame:
    """Attach ROE to candidate DataFrame via Tushare with graceful fallback.

    Strategy:
      1. Try ``fina_indicator`` (requires ~2000 Tushare credits).
      2. If that fails or ``force_tushare_fallback`` is True, estimate ROE
         from ``daily_basic`` (PE ≈ price/earnings, PB ≈ price/book):
         ROE ≈ PB / PE  (a crude but free approximation).
      3. Mark the data source for transparency.
    """
    if df.empty:
        return df.copy()

    result = df.copy()
    token = os.getenv("TUSHARE_TOKEN", "").strip() or os.getenv("TUSHARE_API_TOKEN", "").strip()
    if not token:
        logger.info("No TUSHARE_TOKEN, using daily_basic ROE estimation")
        return _enrich_roe_from_snapshot(result)

    try:
        import tushare as ts
    except ImportError:
        logger.warning("tushare not installed, using daily_basic ROE estimation")
        return _enrich_roe_from_snapshot(result)

    pro = ts.pro_api(token)
    proxy_url = os.getenv("TUSHARE_API_URL", "").strip()
    if proxy_url:
        pro._DataApi__token = token
        pro._DataApi__http_url = proxy_url

    if not force_tushare_fallback:
        try:
            result = _enrich_roe_from_fina_indicator(result, pro)
            if result["roe_source"].notna().any() and (result["roe_source"] == "fina_indicator").any():
                logger.info("ROE enriched via fina_indicator: %d stocks",
                            (result["roe_source"] == "fina_indicator").sum())
                return result
        except Exception as exc:
            logger.warning("fina_indicator failed (%s), falling back to daily_basic estimation", exc)

    # Fallback: use daily_basic to estimate ROE ≈ PB / PE
    try:
        result = _enrich_roe_from_daily_basic_tushare(result, pro)
        est_count = (result["roe_source"] == "daily_basic_est").sum()
        logger.info("ROE estimated via daily_basic: %d stocks", est_count)
        return result
    except Exception as exc:
        logger.warning("daily_basic ROE estimation failed (%s), using snapshot estimation", exc)
        return _enrich_roe_from_snapshot(result)


def _enrich_roe_from_fina_indicator(df: pd.DataFrame, pro) -> pd.DataFrame:
    """Fetch ROE from Tushare fina_indicator for each candidate.

    Uses the most recent quarterly ROE (roe_dt / roe_ttm) available.
    Tries multiple field names for compatibility with different Tushare versions.
    """
    result = df.copy()
    result["roe"] = np.nan
    result["roe_source"] = ""

    codes = list(dict.fromkeys(result["code"].astype(str).str.zfill(6)))
    if not codes:
        return result

    # Fetch latest fina_indicator for all stocks at once
    from alphasift.daily import _to_tushare_code

    ts_codes = [_to_tushare_code(c) for c in codes]

    # Try to get the most recent 2 quarters of data
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=400)).strftime("%Y%m%d")

    roe_map: dict[str, float] = {}
    for ts_code_batch in _batch(ts_codes, 50):
        try:
            finance = pro.fina_indicator(
                ts_code=",".join(ts_code_batch),
                start_date=start_date,
                end_date=end_date,
            )
            if finance is None or finance.empty:
                continue

            # Robust column detection: different Tushare versions use different names
            roe_col = None
            for candidate in ["roe", "roe_dt", "roe_ttm", "roe_yearly"]:
                if candidate in finance.columns:
                    roe_col = candidate
                    break
            if roe_col is None:
                continue

            finance[roe_col] = pd.to_numeric(finance[roe_col], errors="coerce")
            finance = finance.sort_values(["ts_code", "end_date"])

            for ts_code_raw in ts_code_batch:
                sub = finance[finance["ts_code"] == ts_code_raw]
                if sub.empty or sub[roe_col].dropna().empty:
                    continue
                # Use most recent available ROE
                roe_val = float(sub[roe_col].dropna().iloc[-1])
                symbol = ts_code_raw.split(".")[0].zfill(6)
                roe_map[symbol] = roe_val
        except Exception as exc:
            logger.debug("fina_indicator batch failed: %s", exc)
            continue

    for i, row in result.iterrows():
        code_key = str(row["code"]).zfill(6)
        if code_key in roe_map:
            result.at[i, "roe"] = round(roe_map[code_key], 4)
            result.at[i, "roe_source"] = "fina_indicator"

    return result


def _enrich_roe_from_daily_basic_tushare(df: pd.DataFrame, pro) -> pd.DataFrame:
    """Estimate ROE from Tushare daily_basic: ROE ≈ PB / PE.

    This is a rough approximation that works for positive-PE stocks:
      PE = Price / EPS,  PB = Price / BVPS
      → PB / PE = (Price/BVPS) / (Price/EPS) = EPS / BVPS = ROE
    """
    result = df.copy()
    if "roe" not in result.columns:
        result["roe"] = np.nan
    if "roe_source" not in result.columns:
        result["roe_source"] = ""

    # For rows already filled by fina_indicator, skip
    already_done = result["roe_source"] == "fina_indicator"

    # Use snapshot PE/PB if available
    if "pe_ratio" in result.columns and "pb_ratio" in result.columns:
        pe = pd.to_numeric(result["pe_ratio"], errors="coerce")
        pb = pd.to_numeric(result["pb_ratio"], errors="coerce")
        mask = (~already_done) & (pe > 0) & (pb > 0) & pe.notna() & pb.notna()
        result.loc[mask, "roe"] = (pb[mask] / pe[mask] * 100).round(2)
        result.loc[mask, "roe_source"] = "daily_basic_est"
    else:
        # Fall back to fetching daily_basic via Tushare
        try:
            trade_date = _resolve_latest_trade_date(pro)
            basic_df = pro.daily_basic(
                trade_date=trade_date,
                fields="ts_code,pe,pb",
            )
            if basic_df is not None and not basic_df.empty:
                basic_df["symbol"] = basic_df["ts_code"].astype(str).str.split(".").str[0].str.zfill(6)
                basic_df["pe"] = pd.to_numeric(basic_df["pe"], errors="coerce")
                basic_df["pb"] = pd.to_numeric(basic_df["pb"], errors="coerce")
                basic_df["roe_est"] = (basic_df["pb"] / basic_df["pe"] * 100).where(
                    (basic_df["pe"] > 0) & (basic_df["pb"] > 0)
                )
                roe_lookup = dict(zip(basic_df["symbol"], basic_df["roe_est"]))
                for i, row in result.iterrows():
                    code_key = str(row["code"]).zfill(6)
                    if code_key in roe_lookup and not already_done.iloc[i]:
                        val = roe_lookup[code_key]
                        if pd.notna(val):
                            result.at[i, "roe"] = round(float(val), 2)
                            result.at[i, "roe_source"] = "daily_basic_est"
        except Exception as exc:
            logger.debug("daily_basic ROE fetch failed: %s", exc)

    return result


def _enrich_roe_from_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    """Estimate ROE purely from snapshot PE/PB without any Tushare call."""
    result = df.copy()
    result["roe"] = np.nan
    result["roe_source"] = ""
    if "pe_ratio" in result.columns and "pb_ratio" in result.columns:
        pe = pd.to_numeric(result["pe_ratio"], errors="coerce")
        pb = pd.to_numeric(result["pb_ratio"], errors="coerce")
        mask = (pe > 0) & (pb > 0) & pe.notna() & pb.notna()
        result.loc[mask, "roe"] = (pb[mask] / pe[mask] * 100).round(2)
        result.loc[mask, "roe_source"] = "snapshot_est"
    return result


def _resolve_latest_trade_date(pro) -> str:
    """Get latest trading date from Tushare, falling back to weekday calc."""
    from datetime import date

    end = date.today()
    start = end - timedelta(days=10)
    try:
        calendar = pro.trade_cal(
            exchange="SSE",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            is_open="1",
            fields="cal_date",
        )
        if calendar is not None and not calendar.empty and "cal_date" in calendar.columns:
            return str(calendar["cal_date"].max())
    except Exception:
        pass
    # Fallback to recent weekday
    d = end
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def _batch(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]
