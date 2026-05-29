# -*- coding: utf-8 -*-
"""个股 K 线数据接口 — GET /api/v1/stock/{code}/kline

数据源：baostock（独立证券数据服务，不受东方财富 TLS 兼容问题影响）。
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Literal

import baostock as bs
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stock"])

KlinePeriod = Literal["daily", "weekly", "monthly"]

_PERIOD_MAP = {"daily": "d", "weekly": "w", "monthly": "m"}


@router.get("/stock/{code}/kline")
async def get_kline(
    code: str,
    period: KlinePeriod = Query("daily"),
    count: int = Query(100, ge=10, le=500),
):
    try:
        result = await run_in_threadpool(_fetch, code, period, count)
    except Exception as e:
        logger.exception("K线失败: code=%s period=%s", code, period)
        raise HTTPException(status_code=500, detail=str(e))
    return JSONResponse(content=result)


def _fetch(code: str, period: str, count: int) -> dict:
    """通过 baostock 获取 K 线数据。"""
    raw = code.strip().replace(".SH", "").replace(".SZ", "")

    # baostock 代码格式：sh.605589 / sz.000001
    market = "sh" if raw.startswith(("6", "9")) else "sz"
    symbol = f"{market}.{raw}"

    freq = _PERIOD_MAP.get(period, "d")

    end_d = date.today().strftime("%Y-%m-%d")
    start_d = date.today().replace(year=date.today().year - 2).strftime("%Y-%m-%d")

    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")

    try:
        rs = bs.query_history_k_data_plus(
            symbol,
            "date,open,high,low,close,volume,code,name",
            start_date=start_d,
            end_date=end_d,
            frequency=freq,
            adjustflag="2",  # 前复权
        )
        if rs.error_code != "0":
            raise RuntimeError(f"baostock 查询失败: {rs.error_msg}")

        rows = []
        while rs.next():
            rows.append(rs.get_row_data())

        if not rows:
            return {"code": code, "name": "", "period": period, "data": []}

        rows = rows[-count:]

        # 提取名称（取最后一条的名称字段，索引 6=code, 7=name）
        name = rows[-1][7] if len(rows[-1]) > 7 and rows[-1][7] else code

        data = []
        for row in rows:
            try:
                item = {
                    "time": row[0],           # date
                    "open": float(row[1]),    # open
                    "high": float(row[2]),    # high
                    "low": float(row[3]),     # low
                    "close": float(row[4]),   # close
                    "volume": int(float(row[5])),  # volume
                }
                data.append(item)
            except (ValueError, IndexError):
                continue

        logger.info("K线成功: code=%s period=%s count=%d", code, period, len(data))
        return {"code": code, "name": name, "period": period, "data": data}
    finally:
        bs.logout()
