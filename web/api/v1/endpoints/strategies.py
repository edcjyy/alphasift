# -*- coding: utf-8 -*-
"""策略管理接口 — GET/POST/DELETE /api/v1/strategies"""

from __future__ import annotations

import logging
import os
import signal
import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from ..schemas.common import StrategySummary

logger = logging.getLogger(__name__)

router = APIRouter(tags=["strategies"])

# 允许上传的最大文件大小（2MB）
MAX_UPLOAD_SIZE = 2 * 1024 * 1024


def _get_strategies_dir() -> Path:
    """解析当前生效的策略目录。"""
    from alphasift.config import Config

    return Config.from_env().strategies_dir


def _is_restartable() -> bool:
    """判断当前进程是否支持重启（Docker / systemd / 手动启动均可）。"""
    return True


# ---------------------------------------------------------------------------
# GET /strategies — 列出所有策略
# ---------------------------------------------------------------------------


@router.get("/strategies", response_model=list[StrategySummary])
async def list_strategies():
    """返回所有可用选股策略的列表。"""
    from alphasift.strategy import list_strategies

    strategies = await run_in_threadpool(list_strategies)

    return [
        StrategySummary(
            name=s.name,
            display_name=getattr(s, "display_name", s.name),
            description=getattr(s, "description", None),
            version=getattr(s, "version", None),
            category=getattr(s, "category", None),
            tags=getattr(s, "tags", None),
        )
        for s in strategies
    ]


# ---------------------------------------------------------------------------
# GET /strategies/{name} — 查看策略详情（含 YAML 内容）
# ---------------------------------------------------------------------------


@router.get("/strategies/{name}", response_model=dict)
async def get_strategy(name: str):
    """按策略名获取完整信息，包括 YAML 源文件内容。"""
    from alphasift.strategy import list_strategies as _list

    strategies = await run_in_threadpool(_list)

    # 找到对应策略的元信息
    info = None
    for s in strategies:
        if s.name == name:
            info = s
            break
    if info is None:
        raise HTTPException(status_code=404, detail=f"未找到策略: {name}")

    # 查找 YAML 文件内容
    strategies_dir = _get_strategies_dir()
    yaml_content = None
    source = None
    for f in sorted(strategies_dir.glob("*.yaml")):
        try:
            import yaml
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("name") == name:
                yaml_content = f.read_text(encoding="utf-8")
                source = str(f.name)
                break
        except Exception:
            continue

    return {
        "name": info.name,
        "display_name": info.display_name,
        "description": info.description,
        "version": info.version,
        "category": info.category,
        "tags": info.tags,
        "market_scope": getattr(info, "market_scope", None),
        "source_file": source,
        "yaml": yaml_content,
    }


# ---------------------------------------------------------------------------
# POST /strategies/upload — 上传策略文件
# ---------------------------------------------------------------------------


@router.post("/strategies/upload", response_model=dict)
async def upload_strategy(file: UploadFile = File(...)):
    """上传一个 .yaml 策略文件。

    文件会保存到策略目录，上传后需要点击"重启生效"或手动重启容器。
    """
    # 校验文件名
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")

    if not file.filename.endswith((".yaml", ".yml")):
        raise HTTPException(status_code=400, detail="仅支持 .yaml / .yml 文件")

    # 读取内容并限制大小
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail=f"文件过大，最大 {MAX_UPLOAD_SIZE // 1024} KB")

    # 统一使用 .yaml 后缀保存；消毒文件名防止路径遍历
    raw_name = file.filename or "uploaded_strategy"
    # Strip path separators and traversal, keep only safe characters
    safe_stem = Path(raw_name).name  # drops any directory component
    safe_stem = safe_stem.rsplit(".", 1)[0] or safe_stem  # strip extension
    safe_stem = "".join(c for c in safe_stem if c.isalnum() or c in "_-") or "strategy"
    dest_name = f"{safe_stem}.yaml"

    # 校验是否为合法 YAML + 可被 load_strategy 解析
    import yaml
    from alphasift.strategy import load_strategy
    import tempfile

    try:
        yaml.safe_load(content.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"YAML 格式无效: {e}")

    # 写入临时文件做策略验证
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        strategy = load_strategy(tmp_path)
        strategy_name = strategy.name
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"策略定义无效: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)

    # 保存到策略目录
    strategies_dir = _get_strategies_dir()
    dest_path = strategies_dir / dest_name

    if dest_path.exists():
        # 覆盖前备份
        backup_path = dest_path.with_suffix(".yaml.bak")
        shutil.copy2(dest_path, backup_path)

    dest_path.write_bytes(content)

    logger.info("Strategy uploaded: %s → %s", strategy_name, dest_path)

    return {
        "ok": True,
        "name": strategy_name,
        "filename": dest_path.name,
        "message": "策略已保存。需要重启容器或点击「重启生效」按钮使新策略生效。",
    }


# ---------------------------------------------------------------------------
# DELETE /strategies/{name} — 删除策略
# ---------------------------------------------------------------------------


@router.delete("/strategies/{name}", response_model=dict)
async def delete_strategy(name: str):
    """按策略名称删除 .yaml 文件（同时尝试 .yml 后缀）。"""
    strategies_dir = _get_strategies_dir()

    # 先看是否有 name 匹配的 .yaml
    candidates = sorted(strategies_dir.glob("*.yaml")) + sorted(strategies_dir.glob("*.yml"))

    deleted = []
    for f in candidates:
        try:
            import yaml
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("name") == name:
                f.unlink()
                deleted.append(str(f.name))
                logger.info("Strategy deleted: %s (%s)", name, f)
        except Exception:
            continue

    if not deleted:
        raise HTTPException(status_code=404, detail=f"未找到名为 '{name}' 的策略文件")

    return {
        "ok": True,
        "name": name,
        "deleted_files": deleted,
        "message": "策略已删除。需要重启容器或点击「重启生效」按钮使变更生效。",
    }


# ---------------------------------------------------------------------------
# POST /strategies/reload — 重启服务
# ---------------------------------------------------------------------------


@router.post("/strategies/reload", response_model=dict)
async def reload_service():
    """向自身进程发送 SIGTERM，由 Docker restart policy 自动拉起新进程。

    新进程会重新读取策略目录，上传/删除的策略将生效。
    """
    if not _is_restartable():
        raise HTTPException(status_code=500, detail="当前环境不支持重启")

    logger.info("Reload requested by user — sending SIGTERM to self (pid=%d)", os.getpid())

    # 用后台线程延时发送信号，确保 HTTP 响应先返回
    from threading import Timer

    def _shutdown():
        os.kill(os.getpid(), signal.SIGTERM)

    Timer(0.3, _shutdown).start()

    return {
        "ok": True,
        "message": "正在重启服务，请稍候刷新页面...",
    }
