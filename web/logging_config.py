# -*- coding: utf-8 -*-
"""AlphaSift WebUI 日志配置 — 参考 DSA 的 src/logging_config.py"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# 抑制 LiteLLM 等第三方库的冗余日志
THIRD_PARTY_LOGGERS = [
    "httpx",
    "httpcore",
    "openai",
    "urllib3",
    "asyncio",
    "aiohttp",
    "websockets",
    "watchfiles",
    "uvicorn.access",
]


def setup_logging(log_dir: str | None = None, log_level: int = logging.INFO):
    """初始化日志系统。

    控制台: INFO 级别
    文件: DEBUG 级别 → {LOG_DIR}/alphasift.log (10MB x 5 滚动)
    """
    if log_dir is None:
        log_dir = os.getenv("LOG_DIR", "./logs")

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # 避免重复添加 handler（uvicorn reload 等场景）
    if root.handlers:
        root.handlers.clear()

    # ── 控制台 handler (INFO+) ──
    console_fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-7s %(name)s | %(message)s",
        datefmt="%m-%d %H:%M:%S",
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_fmt)
    root.addHandler(console_handler)

    # ── 文件 handler (DEBUG+, 10 MB x 5) ──
    file_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        log_path / "alphasift.log",
        maxBytes=10 * 1024 * 1024,   # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_fmt)
    root.addHandler(file_handler)

    # ── 错误单独文件 ──
    error_handler = RotatingFileHandler(
        log_path / "alphasift_error.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_fmt)
    root.addHandler(error_handler)

    # ── 抑制第三方库日志 ──
    for name in THIRD_PARTY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.handlers = []  # 避免 uvicorn 重复输出
    uvicorn_logger.propagate = True

    logger = logging.getLogger(__name__)
    logger.info("日志系统已初始化: log_dir=%s, level=%s", log_dir, logging.getLevelName(log_level))
