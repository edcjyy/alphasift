# -*- coding: utf-8 -*-
"""定时任务调度接口 — POST/GET/DELETE /api/v1/schedule"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(tags=["schedule"])


# ---------------------------------------------------------------------------
# In-memory task storage (persisted to disk as JSON for restart survival)
# ---------------------------------------------------------------------------

@dataclass
class ScheduleTask:
    id: str
    name: str
    strategy: str
    cron_expr: str          # e.g. "30 9 * * 1-5" (cron syntax)
    enabled: bool = True
    max_output: int = 20
    use_llm: bool = False
    daily_enrich: bool = False
    save_run: bool = True
    created_at: str = ""
    last_run_at: str = ""
    next_run_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_tasks: dict[str, ScheduleTask] = {}
_lock = asyncio.Lock()

# Try to load persisted tasks
import json
import os
from pathlib import Path

_STORAGE_PATH = Path(os.environ.get("ALPHASIFT_DATA_DIR", Path.cwd() / "data")) / ".schedule_tasks.json"


def _load_tasks():
    if _STORAGE_PATH.exists():
        try:
            raw = json.loads(_STORAGE_PATH.read_text(encoding="utf-8"))
            for item in raw:
                t = ScheduleTask(**item)
                _tasks[t.id] = t
            logger.info("已加载 %d 个定时任务", len(_tasks))
        except Exception:
            logger.warning("加载定时任务文件失败，使用空列表")


def _save_tasks():
    try:
        _STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        raw = [t.to_dict() for t in _tasks.values()]
        _STORAGE_PATH.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        logger.exception("保存定时任务失败")


async def _persist():
    """Thread-safe persist."""
    async with _lock:
        _save_tasks()


_load_tasks()


# ---------------------------------------------------------------------------
# Cron parser (minimal, supports 5-field cron: minute hour day month weekday)
# weekdays: 0=Sun, 6=Sat
# ---------------------------------------------------------------------------

CRON_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
               "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
CRON_WDAYS = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}


def _parse_field(field: str, lo: int, hi: int, name_map: dict[str, int] | None = None) -> set[int]:
    """Parse one cron field into a set of valid values ("*", "1,3", "1-5", "*/5", or names)."""
    result: set[int] = set()
    for part in field.split(","):
        part = part.strip().lower()
        if name_map and part in name_map:
            result.add(name_map[part])
            continue
        if part == "*":
            result.update(range(lo, hi + 1))
            continue
        if "/" in part:
            base, step = part.split("/", 1)
            base = base.strip()
            step_val = int(step)
            if base == "*":
                base_range = range(lo, hi + 1)
            else:
                base_range = range(int(base), hi + 1)
            result.update(base_range[::step_val])
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            result.update(range(int(a), int(b) + 1))
            continue
        try:
            result.add(int(part))
        except ValueError:
            pass
    return result


def _next_cron(cron_expr: str, after: float | None = None) -> float | None:
    """Return the next Unix timestamp matching the 5-field cron expression.
    If no future match within 365 days, returns None.
    """
    import calendar

    if not after:
        after = time.time()

    fields = cron_expr.strip().split()
    if len(fields) != 5:
        return None

    mins = _parse_field(fields[0], 0, 59)
    hours = _parse_field(fields[1], 0, 23)
    days = _parse_field(fields[2], 1, 31)
    months = _parse_field(fields[3], 1, 12, CRON_MONTHS)
    wdays = _parse_field(fields[4], 0, 7, CRON_WDAYS)  # 0=Sun, 7 also means Sun

    dt = datetime.fromtimestamp(after, tz=timezone.utc)
    # Search up to 365 days ahead
    for _ in range(366 * 24 * 60):
        dt = dt.replace(second=0, microsecond=0) + __import__("datetime").timedelta(minutes=1)
        if (dt.minute in mins and dt.hour in hours
                and dt.day in days and dt.month in months
                and dt.weekday() in wdays):
            return dt.timestamp()
    return None


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@router.get("/schedule")
async def list_tasks():
    """列出所有定时任务。"""
    async with _lock:
        return [t.to_dict() for t in _tasks.values()]


@router.post("/schedule")
async def create_task(req: dict):
    """创建新的定时任务。"""
    task_id = str(uuid.uuid4())[:8]
    cron_expr = req.get("cron_expr", "").strip()
    if not cron_expr:
        raise HTTPException(status_code=400, detail="cron_expr 不能为空")

    strategy = req.get("strategy", "").strip()
    if not strategy:
        raise HTTPException(status_code=400, detail="strategy 不能为空")

    now = datetime.now(timezone.utc).isoformat()
    next_ts = _next_cron(cron_expr, time.time())
    next_run = datetime.fromtimestamp(next_ts, tz=timezone.utc).isoformat() if next_ts else "N/A"

    task = ScheduleTask(
        id=task_id,
        name=req.get("name", f"Task-{task_id}"),
        strategy=strategy,
        cron_expr=cron_expr,
        enabled=req.get("enabled", True),
        max_output=req.get("max_output", 20),
        use_llm=req.get("use_llm", False),
        daily_enrich=req.get("daily_enrich", False),
        save_run=req.get("save_run", True),
        created_at=now,
        next_run_at=next_run,
    )
    async with _lock:
        _tasks[task_id] = task
        _save_tasks()
    logger.info("创建定时任务 %s: %s [%s]", task_id, task.name, cron_expr)
    return task.to_dict()


@router.put("/schedule/{task_id}")
async def update_task(task_id: str, req: dict):
    """更新定时任务（启用/禁用/修改参数）。"""
    async with _lock:
        if task_id not in _tasks:
            raise HTTPException(status_code=404, detail="任务不存在")
        t = _tasks[task_id]
        for key in ("name", "strategy", "cron_expr", "enabled", "max_output",
                     "use_llm", "daily_enrich", "save_run"):
            if key in req:
                setattr(t, key, req[key])
        if "cron_expr" in req:
            next_ts = _next_cron(t.cron_expr, time.time())
            t.next_run_at = datetime.fromtimestamp(next_ts, tz=timezone.utc).isoformat() if next_ts else "N/A"
        _save_tasks()
    return t.to_dict()


@router.delete("/schedule/{task_id}")
async def delete_task(task_id: str):
    """删除定时任务。"""
    async with _lock:
        if task_id not in _tasks:
            raise HTTPException(status_code=404, detail="任务不存在")
        del _tasks[task_id]
        _save_tasks()
    logger.info("已删除定时任务 %s", task_id)
    return {"status": "ok"}


@router.post("/schedule/{task_id}/run")
async def run_task_now(task_id: str):
    """立即执行一次定时任务。"""
    async with _lock:
        if task_id not in _tasks:
            raise HTTPException(status_code=404, detail="任务不存在")
        t = _tasks[task_id]

    try:
        from alphasift.pipeline import screen
        from starlette.concurrency import run_in_threadpool

        result = await run_in_threadpool(
            screen,
            strategy=t.strategy,
            max_output=t.max_output,
            use_llm=t.use_llm,
            daily_enrich=t.daily_enrich,
        )
        if t.save_run:
            from alphasift.store import save_screen_result
            from alphasift.config import Config
            config = Config.from_env()
            try:
                save_screen_result(result, data_dir=config.data_dir)
            except Exception as exc:
                logger.warning("Schedule save failed: %s", exc)
        async with _lock:
            if task_id in _tasks:
                _tasks[task_id].last_run_at = datetime.now(timezone.utc).isoformat()
                _save_tasks()
        return {"status": "ok", "run_id": getattr(result, "run_id", "N/A")}
    except Exception as e:
        logger.exception("手动执行定时任务 %s 失败", task_id)
        raise HTTPException(status_code=500, detail=str(e))
