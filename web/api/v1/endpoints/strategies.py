# -*- coding: utf-8 -*-
"""策略列表接口 — GET /api/v1/strategies"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from ..schemas.common import StrategySummary

logger = logging.getLogger(__name__)

router = APIRouter(tags=["strategies"])


@router.get("/strategies", response_model=list[StrategySummary])
async def list_strategies():
    """返回所有可用选股策略的列表。"""
    from alphasift.strategy import list_strategies

    strategies = await run_in_threadpool(list_strategies)

    return [
        StrategySummary(
            name=s.name,
            display_name=getattr(s, "display_name", s.name),
            description=getattr(s, "description", None),
            version=getattr(s, "version", None),
            category=getattr(s, "category", None),
            tags=getattr(s, "tags", None),
        )
        for s in strategies
    ]
