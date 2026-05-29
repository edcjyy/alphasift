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


def _transform_eval_result(raw_result, run_id: str) -> dict:
    """将 EvaluationResult（后端 dataclass）转换为前端 EvaluateResult 格式。"""
    picks = raw_result.picks or []

    # 转换每只 pick → 前端字段名
    results = []
    best_r = -999.0
    worst_r = 999.0
    for p in picks:
        r = {
            "code": p.code,
            "name": p.name,
            "rank": p.rank,
            "entry_date": raw_result.created_at or "",
            "entry_price": p.entry_price or 0,
            "exit_date": raw_result.evaluated_at or "",
            "exit_price": p.current_price or 0,
            "return_pct": p.return_pct or 0,
            "max_drawdown_pct": getattr(p, "max_drawdown_pct", 0) or 0,
            "win": getattr(p, "status", "") == "win",
            "final_score": getattr(p, "final_score", 0) or 0,
            "llm_sector": getattr(p, "llm_sector", "") or "",
            "llm_tags": getattr(p, "llm_tags", []) or [],
            "risk_level": getattr(p, "risk_level", "") or "",
        }
        results.append(r)
        rp = r["return_pct"]
        if rp > best_r:
            best_r = rp
        if rp < worst_r:
            worst_r = rp

    # 汇总
    win_count = sum(1 for r in results if r["win"])
    total = len(results)
    summary = {
        "total": total,
        "avg_return_pct": getattr(raw_result, "average_return_pct", 0) or 0,
        "win_rate": win_count / total if total > 0 else 0,
        "max_drawdown_pct": 0,  # EvaluationResult 没有此字段，后续可扩展
        "best_return_pct": best_r if total > 0 else 0,
        "worst_return_pct": worst_r if total > 0 else 0,
    }

    return {
        "run_id": run_id,
        "strategy": raw_result.strategy or "",
        "evaluation_date": raw_result.evaluated_at or "",
        "holding_days": raw_result.elapsed_days or 0,
        "results": results,
        "summary": summary,
        "with_price_path": getattr(raw_result, "path_status", False) or False,
    }


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
        "收到评估请求: run_id=%s, with_price_path=%s",
        run_id,
        req.with_price_path,
    )

    try:
        eval_result = await run_in_threadpool(
            evaluate_saved_run,
            run_id,
            config=config,
            with_price_path=req.with_price_path,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"未找到运行记录: {run_id}")
    except Exception as e:
        logger.exception("评估失败: run_id=%s", run_id)
        raise HTTPException(status_code=500, detail=f"评估失败: {e}")

    # 转换为前端兼容格式
    result_dict = _transform_eval_result(eval_result, run_id)

    logger.info("评估完成: run_id=%s, picks=%d", run_id, result_dict["summary"]["total"])

    return JSONResponse(
        content=EvaluateResponse(run_id=run_id, result=result_dict).model_dump(),
    )
