# -*- coding: utf-8 -*-
"""T+N 评估接口 — POST /api/v1/evaluate/{run_id}"""

from __future__ import annotations

import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from ..schemas.common import EvaluateRequest, EvaluateResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["evaluate"])


@router.post("/evaluate/{run_id}", response_model=EvaluateResponse)
async def run_evaluate(run_id: str, req: EvaluateRequest | None = None):
    """对指定的历史选股运行进行 T+N 回溯评估。

    调用 alphasift.evaluate.evaluate_saved_run() 计算每个 pick 在后续
    交易日中的表现，包括收益率、最大回撤等指标。
    """
    from alphasift.config import Config
    from alphasift.evaluate import evaluate_saved_run

    if req is None:
        req = EvaluateRequest()

    config = Config.from_env()

    logger.info(
        "收到评估请求: run_id=%s, explain=%s, with_price_path=%s",
        run_id,
        req.explain,
        req.with_price_path,
    )

    try:
        eval_result = await run_in_threadpool(
            evaluate_saved_run,
            run_id,
            data_dir=config.data_dir,
            explain=req.explain,
            with_price_path=req.with_price_path,
            config=config,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"未找到运行记录: {run_id}")
    except Exception as e:
        logger.exception("评估失败: run_id=%s", run_id)
        raise HTTPException(status_code=500, detail=f"评估失败: {e}")

    result_dict = asdict(eval_result)

    logger.info("评估完成: run_id=%s", run_id)

    return JSONResponse(
        content=EvaluateResponse(run_id=run_id, result=result_dict).model_dump(),
    )
