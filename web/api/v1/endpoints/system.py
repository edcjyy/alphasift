# -*- coding: utf-8 -*-
"""系统健康检查与信息接口 — GET /api/v1/system/..."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from ..schemas.common import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


@router.get("/system/health", response_model=HealthResponse)
async def health():
    """系统健康检查。

    返回系统状态及各项子服务的可用性信息，包括：
    - 数据目录状态
    - 数据源可用性
    - LLM 配置状态
    - DSA（Data Snapshot Archive）连通性
    """
    from alphasift.config import Config

    config = Config.from_env()

    details: dict = {
        "data_dir": str(config.data_dir),
    }

    # 检查数据源可用性
    try:
        snapshot_sources = getattr(config, "snapshot_sources", None)
        if snapshot_sources:
            details["snapshot_sources"] = list(snapshot_sources)
        else:
            details["snapshot_sources"] = "未配置"
    except Exception as e:
        details["snapshot_sources"] = f"读取失败: {e}"

    # LLM 配置状态
    llm_model = getattr(config, "llm_model", None) or getattr(config, "default_llm_model", None)
    details["llm_model"] = llm_model or "未配置"
    details["llm_status"] = "已配置" if llm_model else "未配置"

    # DSA 连通性
    dsa_url = getattr(config, "dsa_url", None) or getattr(config, "dsa_base_url", None)
    details["dsa_url"] = dsa_url or "未配置"

    dsa_reachable = False
    if dsa_url:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{dsa_url.rstrip('/')}/health")
                dsa_reachable = resp.status_code < 500
        except Exception:
            dsa_reachable = False
    details["dsa_reachable"] = dsa_reachable

    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
        details=details,
    )
