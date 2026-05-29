# -*- coding: utf-8 -*-
"""选股执行接口 — POST /api/v1/screen + GET /screen/status/{task_id}"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from dataclasses import asdict

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from ..schemas.common import ScreenRequest, ScreenResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["screen"])

# ---------------------------------------------------------------------------
# In-memory progress tracker (thread-safe)
# ---------------------------------------------------------------------------
_progress: dict[str, dict] = {}
_progress_lock = threading.Lock()

STAGES = [
    "init",           # 初始化
    "loading_strategy", # 加载策略
    "fetching_snapshot", # 获取行情快照
    "applying_filters",  # 应用筛选条件
    "enriching_daily",   # 补充日线数据
    "scoring",           # 计算评分
    "llm_ranking",       # LLM排序
    "post_analysis",     # 后置分析
    "saving",            # 保存结果
    "done",              # 完成
    "error",             # 错误
]


def _update_progress(task_id: str, stage: str, message: str = "", pct: int = 0):
    with _progress_lock:
        _progress[task_id] = {
            "stage": stage,
            "message": message,
            "pct": min(100, max(0, pct)),
            "updated_at": time.time(),
        }


# ---------------------------------------------------------------------------
# POST /screen — 运行选股（带进度追踪）
# ---------------------------------------------------------------------------


@router.post("/screen", response_model=ScreenResponse)
async def run_screen(
    req: ScreenRequest,
    background_tasks: BackgroundTasks,
):
    """运行一次选股流程。返回 task_id 用于轮询进度。"""
    from alphasift.config import Config
    from alphasift.pipeline import screen

    config = Config.from_env()
    task_id = uuid.uuid4().hex[:8]

    _update_progress(task_id, "init", "准备开始选股...", 0)
    logger.info("选股请求: strategy=%s task=%s", req.strategy, task_id)

    def _run_with_progress():
        try:
            _update_progress(task_id, "loading_strategy", f"加载策略 {req.strategy}...", 5)
            _update_progress(task_id, "fetching_snapshot", "获取全市场行情快照...", 10)

            result = screen(
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

            _update_progress(task_id, "scoring", "计算因子评分...", 60)
            after_filter = result.after_filter_count

            if req.use_llm:
                _update_progress(task_id, "llm_ranking", "LLM 智能排序中...", 75)

            _update_progress(task_id, "post_analysis", "后置分析...", 90)

            # save_run
            if req.save_run:
                _update_progress(task_id, "saving", "保存选股结果...", 95)
                from alphasift.store import save_screen_result
                try:
                    save_screen_result(result, data_dir=config.data_dir)
                except Exception as exc:
                    logger.warning("Failed to save: %s", exc)

            _update_progress(task_id, "done", f"完成! 选出 {len(result.picks)} 只候选股", 100)
            return result

        except Exception as e:
            logger.exception("Screen failed: %s", e)
            _update_progress(task_id, "error", str(e)[:100], 0)
            raise

    try:
        result = await run_in_threadpool(_run_with_progress)
    except Exception as e:
        _update_progress(task_id, "error", str(e)[:100], 0)
        raise HTTPException(status_code=500, detail=str(e))

    result_dict = asdict(result)
    run_id = result_dict.get("run_id")

    logger.info("选股完成: strategy=%s run=%s picks=%d", req.strategy, run_id, len(result_dict.get("picks", [])))

    return JSONResponse(
        content=ScreenResponse(run_id=run_id, result=result_dict, task_id=task_id).model_dump(),
    )


# ---------------------------------------------------------------------------
# GET /screen/status/{task_id} — 轮询选股进度
# ---------------------------------------------------------------------------


@router.get("/screen/status/{task_id}")
async def screen_status(task_id: str):
    """获取选股任务的实时进度。前端每秒轮询一次。"""
    with _progress_lock:
        if task_id not in _progress:
            raise HTTPException(status_code=404, detail="任务不存在或已过期")
        status = dict(_progress[task_id])
        # Clean up old completed tasks (> 5 min)
        now = time.time()
        to_remove = [tid for tid, s in _progress.items() if now - s["updated_at"] > 300]
        for tid in to_remove:
            del _progress[tid]

    return {
        "task_id": task_id,
        "stage": status["stage"],
        "message": status["message"],
        "pct": status["pct"],
        "stages": STAGES,
    }
