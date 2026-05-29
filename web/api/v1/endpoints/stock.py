# -*- coding: utf-8 -*-
"""个股 K 线数据接口 — GET /api/v1/stock/{code}/kline"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stock"])

KlinePeriod = Literal["daily", "weekly", "monthly", "5min", "60min"]


@router.get("/stock/{code}/kline")
async def get_kline(
    code: str,
    period: KlinePeriod = Query("daily", description="daily|weekly|monthly|5min|60min"),
    count: int = Query(100, ge=10, le=500, description="返回条数"),
):
    """获取个股 OHLCV K 线数据。

    返回格式：{ code, name, period, data: [{time,open,high,low,close,volume}] }
    time 为 ISO 格式字符串（前端 lightweight-charts 兼容）。
    """
    try:
        result = await run_in_threadpool(_fetch_kline, code, period, count)
    except Exception as e:
        logger.exception("获取K线失败: code=%s period=%s", code, period)
        raise HTTPException(status_code=500, detail=f"获取K线失败: {e}")

    return JSONResponse(content=result)


def _fetch_kline(code: str, period: str, count: int) -> dict:
    """同步获取 K 线数据（在线程池中运行）。"""
    # 格式化为 akshare 需要的代码格式
    # 上交所: 6xxxxx → sh600000; 深交所: 0xxxxx/3xxxxx → sz000001
    raw = code.strip().replace(".SH", "").replace(".SZ", "")
    if raw.startswith(("6", "9")):
        symbol = f"sh{raw}"
    else:
        symbol = f"sz{raw}"

    # 周期映射
    period_map = {
        "daily": "daily",
        "weekly": "weekly",
        "monthly": "monthly",
        "5min": "5",
        "60min": "60",
    }
    ak_period = period_map.get(period, "daily")

    try:
        import akshare as ak
    except ImportError:
        raise HTTPException(status_code=500, detail="akshare 未安装，请执行: pip install akshare")

    from datetime import date

    end_d = date.today().strftime("%Y%m%d")
    start_d = date.today().replace(year=date.today().year - 2).strftime("%Y%m%d")

    # 获取K线
    df = ak.stock_zh_a_hist(
        symbol=raw,
        period=ak_period,
        start_date=start_d,
        end_date=end_d,
        adjust="qfq",
    )

    if df is None or df.empty:
        return {"code": code, "name": "", "period": period, "data": []}

    df = df.tail(count)

    # 提取名称
    name = ""
    if "股票代码" in df.columns:
        name = str(df["股票代码"].iloc[-1]) if len(df) > 0 else ""
    elif "名称" in df.columns:
        name = str(df["名称"].iloc[-1]) if len(df) > 0 else ""

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
