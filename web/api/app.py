# -*- coding: utf-8 -*-
"""AlphaSift Web API — FastAPI 应用工厂。"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .v1.router import router as v1_router

logger = logging.getLogger(__name__)

# 默认 Web 静态文件目录（相对于 web/ 目录）
_DEFAULT_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app(static_dir: str | None = None) -> FastAPI:
    """创建并配置 FastAPI 应用实例。

    Parameters
    ----------
    static_dir : str | None
        前端静态文件目录的绝对路径。如果为 None，则使用默认的 web/static/。

    Returns
    -------
    FastAPI
        已配置好中间件和路由的应用实例。
    """
    app = FastAPI(
        title="AlphaSift Web API",
        description="AlphaSift 自动选股系统 Web 服务",
        version="1.0.0",
    )

    # ── 初始化文件日志（Docker 部署时 LOG_DIR 挂载到 NAS） ──
    try:
        from web.logging_config import setup_logging
        setup_logging()
    except Exception:
        pass  # 非 web 包安装环境（CLI 模式）静默跳过

    # --------------------------------------------------------------------------
    # CORS 中间件（内网工具，允许所有来源）
    # --------------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite dev server
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --------------------------------------------------------------------------
    # 注册 v1 API 路由
    # --------------------------------------------------------------------------
    app.include_router(v1_router)

    # --------------------------------------------------------------------------
    # 健康检查端点
    # --------------------------------------------------------------------------
    @app.get("/api/health")
    async def api_health():
        return JSONResponse({"status": "ok"})

    # --------------------------------------------------------------------------
    # 静态文件托管
    # --------------------------------------------------------------------------
    static_path = Path(static_dir) if static_dir else _DEFAULT_STATIC_DIR

    @app.get("/")
    async def root():
        """根路由返回 index.html"""
        index_file = static_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse({"message": "AlphaSift API is running"})

    @app.get("/{full_path:path}")
    async def serve_static(full_path: str):
        """SPA fallback：静态文件直接返回；缺失文件返回 index.html"""
        file_path = static_path / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # SPA fallback — 所有非 API 路径回退到 index.html
        index_file = static_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse(
            status_code=404,
            content={"detail": "页面未找到"},
        )

    logger.info(
        "AlphaSift API 应用已创建 (static_dir=%s)",
        static_path,
    )

    return app
