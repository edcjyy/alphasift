# -*- coding: utf-8 -*-
# AlphaSift WebUI — 多阶段 Docker 构建
# Stage 1: 前端构建
# Stage 2: Python 后端运行时

# ============================================================
# Stage 1: 前端构建
# ============================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/web/frontend

COPY web/frontend/package.json web/frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY web/frontend/ ./
RUN npm run build

# ============================================================
# Stage 2: Python 运行时
# ============================================================
FROM python:3.12-slim-bookworm

WORKDIR /app

# 系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY pyproject.toml ./
RUN pip install --no-cache-dir "." && \
    pip install --no-cache-dir ".[web]"

# 核心代码
COPY alphasift/ alphasift/
COPY strategies/ strategies/

# Web API 层
COPY web/api/ web/api/

# 前端构建产物（来自 Stage 1）
COPY --from=frontend-builder /app/web/frontend/dist web/static/

# 数据目录
RUN mkdir -p /app/data/runs /app/data/reports

# 非 root 用户
RUN groupadd -g 1000 alphasift && \
    useradd -u 1000 -g alphasift -m -s /bin/bash alphasift && \
    chown -R alphasift:alphasift /app
USER alphasift

# 环境变量
ENV ALPHASIFT_DATA_DIR=/app/data
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

CMD ["uvicorn", "web.api.app:create_app", "--host", "0.0.0.0", "--port", "8080", "--factory"]
