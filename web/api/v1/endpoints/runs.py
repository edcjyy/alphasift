# -*- coding: utf-8 -*-
"""运行记录接口 — GET /api/v1/runs 及相关端点"""

from __future__ import annotations

import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from ..schemas.common import RunDetail, RunSummary

logger = logging.getLogger(__name__)

router = APIRouter(tags=["runs"])


@router.get("/runs", response_model=list[RunSummary])
async def list_runs(limit: int = 20, strategy: str | None = None):
    """列出历史选股运行记录。

    可选按 strategy 过滤；默认返回最近 20 条。
    """
    from alphasift.config import Config
    from alphasift.store import list_saved_runs

    config = Config.from_env()

    runs_raw = await run_in_threadpool(
        list_saved_runs,
        data_dir=config.data_dir,
        limit=limit,
    )

    # list_saved_runs 返回 dict 列表，直接映射为 RunSummary
    summaries = []
    for r in runs_raw:
        # 如果指定了策略过滤，在此处理
        if strategy and r.get("strategy") != strategy:
            continue
        summaries.append(
            RunSummary(
                run_id=r.get("run_id", ""),
                strategy=r.get("strategy", ""),
                created_at=str(r.get("created_at", "")),
                picks_count=r.get("picks_count", 0),
                snapshot_source=r.get("snapshot_source"),
            )
        )

    return summaries


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: str):
    """获取单次运行记录的完整数据。

    从本地存储加载 ScreenResult 并序列化返回。
    """
    from alphasift.config import Config
    from alphasift.store import load_screen_result

    config = Config.from_env()

    logger.info("加载运行记录: run_id=%s", run_id)

    try:
        screen_result = await run_in_threadpool(
            load_screen_result,
            run_id,
            data_dir=config.data_dir,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"未找到运行记录: {run_id}")
    except Exception as e:
        logger.exception("加载运行记录失败: run_id=%s", run_id)
        raise HTTPException(status_code=500, detail=f"加载失败: {e}")

    result_dict = asdict(screen_result)

    return JSONResponse(
        content=RunDetail(run_id=run_id, result=result_dict).model_dump(),
    )
