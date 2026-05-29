# -*- coding: utf-8 -*-
"""个股 K 线数据接口 — GET /api/v1/stock/{code}/kline"""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stock"])

KlinePeriod = Literal["daily", "weekly", "monthly"]

# 东方财富 API 连接不稳定时重试次数
_KLINE_RETRIES = 3
_KLINE_RETRY_DELAY = 2.0  # 秒


@router.get("/stock/{code}/kline")
async def get_kline(
    code: str,
    period: KlinePeriod = Query("daily", description="daily|weekly|monthly"),
    count: int = Query(100, ge=10, le=500, description="返回条数"),
):
    """获取个股 OHLCV K 线数据。

    返回格式：{ code, name, period, data: [{time,open,high,low,close,volume}] }
    """
    try:
        result = await run_in_threadpool(_fetch_kline, code, period, count)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取K线失败: code=%s period=%s", code, period)
        raise HTTPException(status_code=500, detail=f"获取K线失败: {e}")

    return JSONResponse(content=result)


def _fetch_kline(code: str, period: str, count: int) -> dict:
    """同步获取 K 线数据（在线程池中运行，带重试）。"""
    raw = code.strip().replace(".SH", "").replace(".SZ", "")

    period_map = {"daily": "daily", "weekly": "weekly", "monthly": "monthly"}
    ak_period = period_map.get(period, "daily")

    try:
        import akshare as ak
    except ImportError:
        raise HTTPException(status_code=500, detail="akshare 未安装，请执行: pip install akshare")

    end_d = date.today().strftime("%Y%m%d")
    start_d = date.today().replace(year=date.today().year - 2).strftime("%Y%m%d")

    last_err = None
    for attempt in range(1, _KLINE_RETRIES + 1):
        try:
            df = ak.stock_zh_a_hist(
                symbol=raw,
                period=ak_period,
                start_date=start_d,
                end_date=end_d,
                adjust="qfq",
            )
            if df is not None and not df.empty:
                break
        except Exception as e:
            last_err = e
            if attempt < _KLINE_RETRIES:
                logger.warning(
                    "K线获取重试 %d/%d: code=%s period=%s err=%s",
                    attempt, _KLINE_RETRIES, code, period, e,
                )
                time.sleep(_KLINE_RETRY_DELAY * attempt)
            else:
                raise

    if last_err and (df is None or df.empty):
        raise RuntimeError(
            f"东方财富数据接口暂时不可用（已重试{_KLINE_RETRIES}次），请稍后再试"
        )

    if df is None or df.empty:
        return {"code": code, "name": "", "period": period, "data": []}

    df = df.tail(count)

    # 提取名称
    name = ""
    if "名称" in df.columns:
        name = str(df["名称"].iloc[-1]) if len(df) > 0 else ""
    elif "股票代码" in df.columns:
        name = str(df["股票代码"].iloc[-1]) if len(df) > 0 else ""

    # 转换为标准 OHLCV 格式
    data = []
    for _, row in df.iterrows():
        item = {
            "time": str(row["日期"])[:10],
            "open": float(row["开盘"]),
            "high": float(row["最高"]),
            "low": float(row["最低"]),
            "close": float(row["收盘"]),
            "volume": int(row.get("成交量", 0) or 0),
        }
        data.append(item)

    logger.info("K线获取成功: code=%s period=%s count=%d", code, period, len(data))
    return {
        "code": code,
        "name": name or code,
        "period": period,
        "data": data,
    }
