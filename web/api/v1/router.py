# -*- coding: utf-8 -*-
"""AlphaSift Web API v1 路由聚合。"""

from fastapi import APIRouter

from .endpoints import evaluate, reflection, runs, schedule, screen, stock, strategies, system

router = APIRouter(prefix="/api/v1")

# 注册各端点模块的路由
router.include_router(screen.router)
router.include_router(runs.router)
router.include_router(evaluate.router)
router.include_router(strategies.router)
router.include_router(system.router)
router.include_router(schedule.router)
router.include_router(stock.router)
router.include_router(reflection.router)
