# -*- coding: utf-8 -*-
"""Reflection Layer API — strategy evolution analysis endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reflection"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ReflectionRequest(BaseModel):
    run_id: str
    apply: bool = False
    dry_run: bool = False
    min_confidence: float = 0.5


class StrategyChangeOut(BaseModel):
    change_type: str
    target: str
    old_value: str
    new_value: str
    reason: str
    confidence: float


class ReflectionResponse(BaseModel):
    run_id: str
    strategy: str
    diagnosis: str
    summary: str = ""
    changes: list[StrategyChangeOut] = []
    passed_count: int = 0
    rejected_count: int = 0
    critic_score: float = 1.0
    applied: bool = False
    win_rate: float | None = None
    avg_return_pct: float | None = None
    pick_count: int = 0


class MetaLearnResponse(BaseModel):
    total_records: int = 0
    total_strategies: int = 0
    overall_success_rate: float = 0.0
    change_stats: list[dict] = []
    recommendations: list[str] = []


class HistoryRecord(BaseModel):
    id: int
    strategy: str
    run_id: str
    timestamp: str
    win_rate_before: float | None = None
    avg_return_before: float | None = None
    diagnosis: str = ""
    changes: list[dict] = []
    improved: bool | None = None


# ---------------------------------------------------------------------------
# POST /reflection/analyze — run reflection analysis
# ---------------------------------------------------------------------------


@router.post("/reflection/analyze", response_model=ReflectionResponse)
async def reflection_analyze(req: ReflectionRequest):
    """运行 Reflection Layer 分析：加载评估结果 → LLM 诊断 → critic 验证 → 可选应用修改。

    dry_run=True 时预览修改不实际写入，apply=True 时自动应用验证通过的修改。
    """
    from alphasift.reflection import reflect_on_evaluation

    result = await run_in_threadpool(
        reflect_on_evaluation,
        run_id=req.run_id,
        apply=req.apply and not req.dry_run,
        dry_run=req.dry_run,
        min_confidence=req.min_confidence,
    )

    return ReflectionResponse(
        run_id=result.run_id,
        strategy=result.strategy,
        diagnosis=result.diagnosis,
        summary=result.summary,
        changes=[
            StrategyChangeOut(
                change_type=c.change_type,
                target=c.target,
                old_value=c.old_value,
                new_value=c.new_value,
                reason=c.reason,
                confidence=c.confidence,
            )
            for c in result.changes
        ],
        win_rate=result.win_rate,
        avg_return_pct=result.avg_return_pct,
        pick_count=result.pick_count,
    )


# ---------------------------------------------------------------------------
# GET /reflection/history/{strategy} — get evolution history
# ---------------------------------------------------------------------------


@router.get("/reflection/history/{strategy}", response_model=list[HistoryRecord])
async def reflection_history(strategy: str, limit: int = 20):
    """获取指定策略的进化历史记录。"""
    from alphasift.config import Config
    from alphasift.reflection.experience import get_history

    config = Config.from_env()

    records = await run_in_threadpool(
        get_history,
        strategy=strategy,
        data_dir=config.data_dir,
        limit=limit,
    )

    import json
    result = []
    for r in records:
        changes = []
        try:
            if isinstance(r.get("changes_json"), str):
                changes = json.loads(r["changes_json"])
        except Exception:
            pass

        result.append(HistoryRecord(
            id=r.get("id", 0),
            strategy=r.get("strategy", strategy),
            run_id=r.get("run_id", ""),
            timestamp=str(r.get("timestamp", "")),
            win_rate_before=r.get("win_rate_before"),
            avg_return_before=r.get("avg_return_before"),
            diagnosis=r.get("diagnosis", "") or "",
            changes=changes,
            improved=bool(r["improved"]) if r.get("improved") is not None else None,
        ))

    return result


# ---------------------------------------------------------------------------
# GET /reflection/meta-learn — meta-learning dashboard
# ---------------------------------------------------------------------------


@router.get("/reflection/meta-learn", response_model=MetaLearnResponse)
async def reflection_meta_learn():
    """元学习分析：从历史进化记录中学习最优修改模式。"""
    from alphasift.config import Config
    from alphasift.reflection.meta_learner import learn as meta_learn_fn

    config = Config.from_env()

    result = await run_in_threadpool(
        meta_learn_fn,
        data_dir=config.data_dir,
    )

    return MetaLearnResponse(
        total_records=result.total_records,
        total_strategies=result.total_strategies,
        overall_success_rate=result.overall_success_rate,
        change_stats=[
            {
                "change_type": s.change_type,
                "count": s.count,
                "improved_count": s.improved_count,
                "success_rate": s.success_rate,
            }
            for s in result.change_stats
        ],
        recommendations=result.recommendations,
    )
