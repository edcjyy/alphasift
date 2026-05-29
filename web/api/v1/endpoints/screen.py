# -*- coding: utf-8 -*-
"""选股执行接口 — POST /api/v1/screen"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from ..schemas.common import ScreenRequest, ScreenResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["screen"])


@router.post("/screen", response_model=ScreenResponse)
async def run_screen(
    req: ScreenRequest,
    background_tasks: BackgroundTasks,
):
    """运行一次选股流程。

    该接口会在线程池中调用 alphasift.pipeline.screen()，避免阻塞事件循环。
    选股过程通常耗时 30–60 秒，调用期间不设置超时限制。
    """
    from alphasift.config import Config
    from alphasift.pipeline import screen

    config = Config.from_env()

    logger.info("收到选股请求: strategy=%s, save_run=%s", req.strategy, req.save_run)

    # 将同步的 screen() 调用放到线程池中执行，避免阻塞 asyncio 事件循环
    result = await run_in_threadpool(
        screen,
        req.strategy,
        market="cn",
        max_output=req.max_output,
        use_llm=req.use_llm,
        daily_enrich=req.daily_enrich,
        post_analyzers=req.post_analyzers,
        config=config,
        llm_context=req.context,
        llm_context_files=req.context_files,
        candidate_context_files=req.candidate_context_files,
        collect_llm_candidate_context=req.collect_candidate_context,
        candidate_context_max_candidates=req.candidate_context_max_candidates,
        candidate_context_providers=req.candidate_context_providers,
    )

    # save_run: screen() 本身不保存，需要在调用后手动保存
    if req.save_run:
        from alphasift.store import save_screen_result
        try:
            save_screen_result(result, data_dir=config.data_dir)
        except Exception as exc:
            logger.warning("Failed to save screen result: %s", exc)

    # ScreenResult 是 dataclass，序列化为 dict 返回
    result_dict = asdict(result)

    # 如果 save_run=True，run_id 通常会出现在返回值的某个字段中
    run_id = result_dict.get("run_id")

    logger.info(
        "选股完成: strategy=%s, run_id=%s, picks=%d",
        req.strategy,
        run_id,
        len(result_dict.get("picks", [])),
    )

    return JSONResponse(
        content=ScreenResponse(run_id=run_id, result=result_dict).model_dump(),
    )
