# -*- coding: utf-8 -*-
"""系统健康检查与信息接口 — GET /api/v1/system/..."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..schemas.common import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])

# ---------------------------------------------------------------------------
# .env 可配置环境变量白名单
#  only keys in this list can be read/updated via the API.
# ---------------------------------------------------------------------------
ENV_WHITELIST = {
    # LLM — LiteLLM 主体系（推荐）
    "LITELLM_MODEL",
    "LITELLM_FALLBACK_MODELS",
    "LLM_CHANNELS",
    "LITELLM_CONFIG",
    # LLM — 旧版兼容
    "LLM_MODEL",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_TEMPERATURE",
    "LLM_CONTEXT",
    "LLM_JSON_MODE",
    "LLM_SILENT",
    "LLM_RANK_WEIGHT",
    "OPENAI_BASE_URL",
    # LLM — 候选上下文
    "LLM_CANDIDATE_MULTIPLIER",
    "LLM_MAX_CANDIDATES",
    "LLM_MAX_RETRIES",
    "LLM_MIN_COVERAGE",
    "LLM_CONTEXT_MAX_CHARS",
    "LLM_CANDIDATE_CONTEXT_ENABLED",
    "LLM_CANDIDATE_CONTEXT_MAX_CANDIDATES",
    "LLM_CANDIDATE_CONTEXT_PROVIDERS",
    "LLM_CANDIDATE_CONTEXT_NEWS_LIMIT",
    "LLM_CANDIDATE_CONTEXT_ANNOUNCEMENT_LIMIT",
    "LLM_CANDIDATE_CONTEXT_CACHE_ENABLED",
    "LLM_CANDIDATE_CONTEXT_CACHE_TTL_HOURS",
    # snapshot data source
    "SNAPSHOT_SOURCE_PRIORITY",
    "TUSHARE_API_URL",
    "TUSHARE_TOKEN",
    "TUSHARE_API_TOKEN",
    "TUSHARE_TRADE_DATE",
    # DSA
    "DSA_API_URL",
    "DSA_REPORT_TYPE",
    "DSA_MAX_PICKS",
    "DSA_TIMEOUT_SEC",
    "DSA_FORCE_REFRESH",
    "DSA_NOTIFY",
    # post-analyzers
    "POST_ANALYZERS",
    "POST_ANALYSIS_MAX_PICKS",
    "POST_ANALYZER_URL",
    "POST_ANALYZER_TIMEOUT_SEC",
    # risk
    "RISK_ENABLED",
    "RISK_MAX_PENALTY",
    "RISK_VETO_HIGH",
    # portfolio diversity
    "PORTFOLIO_DIVERSITY_ENABLED",
    "PORTFOLIO_MAX_SAME_LLM_SECTOR",
    "PORTFOLIO_CONCENTRATION_PENALTY",
    # daily enrichment
    "DAILY_ENRICH_ENABLED",
    "DAILY_ENRICH_MAX_CANDIDATES",
    "DAILY_LOOKBACK_DAYS",
    "DAILY_SOURCE",
    "DAILY_FETCH_RETRIES",
    # evaluation
    "EVALUATION_COST_BPS",
    "EVALUATION_FOLLOW_THROUGH_PCT",
    "EVALUATION_FAILED_BREAKOUT_PCT",
    "EVALUATION_PRICE_PATH_ENABLED",
    "EVALUATION_PRICE_PATH_LOOKBACK_DAYS",
    # data dir
    "ALPHASIFT_DATA_DIR",
    "LOG_DIR",
    "STRATEGIES_DIR",
    # industry
    "INDUSTRY_MAP_FILES",
    "INDUSTRY_PROVIDER",
    "INDUSTRY_PROVIDER_MAX_BOARDS",
}

# Keys that contain secrets — mask on read, never echo back full value
ENV_SENSITIVE_KEYS = {
    "TUSHARE_TOKEN",      # Tushare Pro token — 始终脱敏
    "TUSHARE_API_TOKEN",  # alias
    # LLM API Keys — 所有渠道和通用 Key 均脱敏
    "LLM_API_KEY",
    "LLM_OPENAI_API_KEY",
    "LLM_MINIMAX_API_KEY",
    "LLM_DEEPSEEK_API_KEY",
    "LLM_GEMINI_API_KEY",
    "LLM_ANTHROPIC_API_KEY",
    "LLM_QWEN_API_KEY",
    "LLM_ZHIPU_API_KEY",
    "LLM_MOONSHOT_API_KEY",
    "LLM_DASHSCOPE_API_KEY",
    "LLM_SILICONFLOW_API_KEY",
    "LLM_OPENROUTER_API_KEY",
    "LLM_VOLCENGINE_API_KEY",
    "LLM_OLLAMA_API_KEY",
    "LLM_AIHUBMIX_API_KEY",
    "LLM_ANSPIRE_API_KEY",
    # Channel API Keys (LLM_{NAME}_API_KEYS 批量格式)
    "LLM_OPENAI_API_KEYS",
    "LLM_MINIMAX_API_KEYS",
    "LLM_DEEPSEEK_API_KEYS",
    "LLM_GEMINI_API_KEYS",
    "LLM_ANTHROPIC_API_KEYS",
    # LiteLLM 配置路径（可能含 token）
    "LITELLM_CONFIG",
    # 搜索引擎
    "BOCHA_API_KEYS",
    "TAVILY_API_KEY",
}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class EnvEntry(BaseModel):
    key: str
    value: str
    masked: bool = False


class EnvUpdateRequest(BaseModel):
    changes: dict[str, str]  # key -> new value


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _find_env_file() -> str | None:
    """Locate the .env file on disk (same logic as config._load_env_file)."""
    import os
    from pathlib import Path

    candidates = []
    raw = os.environ.get("ALPHASIFT_ENV_FILE", "")
    if raw:
        candidates.append(Path(raw))
    raw2 = os.environ.get("ALPHASIFT_ENV_FILES", "")
    if raw2:
        for item in raw2.replace(os.pathsep, ",").split(","):
            item = item.strip()
            if item:
                candidates.append(Path(item))
    candidates.append(Path(os.getcwd()) / ".env")
    # project root = two levels up from web/api/v1/endpoints/
    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    candidates.append(project_root / ".env")
    seen: set[Path] = set()
    for p in candidates:
        if p in seen:
            continue
        seen.add(p)
        if p.is_file():
            return str(p)
    return None


def _mask_value(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if len(value) <= 6:
        return "****"
    return value[:3] + "****" + value[-3:]


def _parse_env_content(text: str) -> tuple[list[tuple[int, str]], dict[str, str]]:
    """Parse a .env file.

    Returns:
        lines_info: list of (line_index, raw_line) for KEY=VALUE lines
        key_to_value: dict of current values
    """
    lines_info: list[tuple[int, str]] = []
    key_to_value: dict[str, str] = {}
    for i, raw_line in enumerate(text.splitlines()):
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip("'\"")
        lines_info.append((i, raw_line))
        key_to_value[key] = val
    return lines_info, key_to_value


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("/system/env", response_model=list[EnvEntry])
async def get_env():
    """读取白名单内的环境变量（敏感值脱敏）。"""
    import os
    from pathlib import Path

    result: list[EnvEntry] = []

    # 1) read from actual os.environ for currently active values
    for key in sorted(ENV_WHITELIST):
        value = os.environ.get(key, "")
        masked = key in ENV_SENSITIVE_KEYS
        result.append(EnvEntry(key=key, value=_mask_value(value) if masked and value else (value or ""), masked=masked))

    # 2) also read .env file to show values that are set but maybe not yet active
    env_path = _find_env_file()
    if env_path:
        try:
            text = Path(env_path).read_text(encoding="utf-8")
            _, file_values = _parse_env_content(text)
            for entry in result:
                if entry.key in file_values and not os.environ.get(entry.key):
                    v = file_values[entry.key]
                    entry.value = _mask_value(v) if entry.masked and v else (v or "")
        except Exception:
            pass

    return result


@router.put("/system/env")
async def update_env(req: EnvUpdateRequest):
    """更新白名单内的环境变量，写入 .env 文件。

    ⚠️  部分变量需要重启后端才能生效（已标注 requires_restart）。
    """
    import os

    invalid = [k for k in req.changes if k not in ENV_WHITELIST]
    if invalid:
        raise HTTPException(status_code=400, detail=f"不允许修改的变量: {', '.join(invalid)}")

    env_path = _find_env_file()
    if not env_path:
        # create .env at project root
        project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        env_path = str(project_root / ".env")
        logger.info("创建新的 .env 文件: %s", env_path)
        lines = []
    else:
        try:
            with open(env_path, encoding="utf-8") as f:
                lines = f.read().splitlines(keepends=True)
        except Exception as e:
            logger.exception("读取 .env 失败")
            raise HTTPException(status_code=500, detail=f"读取 .env 失败: {e}")

    # Build a map line_idx -> (key, current_value, raw_line)
    # We need to preserve comments and blank lines.
    key_line_map: dict[str, int] = {}  # key -> line index in `lines`
    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        key_line_map[key] = i

    # Apply changes
    changed_keys: list[str] = []
    for key, new_value in req.changes.items():
        new_value = new_value.strip()
        if key in key_line_map:
            idx = key_line_map[key]
            old_line = lines[idx]
            # preserve leading whitespace and comment
            # simple strategy: replace everything after the first =
            eq_pos = old_line.find("=")
            if eq_pos >= 0:
                # preserve the part before "=" (key + whitespace)
                prefix = old_line[:eq_pos + 1]
                # new line keeps original newline
                new_line = prefix.rstrip() + f" {new_value}" + ("\n" if old_line.endswith("\n") else "")
                lines[idx] = new_line
            else:
                lines[idx] = f"{key}={new_value}\n"
        else:
            # append new line
            lines.append(f"{key}={new_value}\n")
        changed_keys.append(key)
        # Also update os.environ so the *currently running process* picks it up
        os.environ[key] = new_value

    # Write back
    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        logger.info("已更新 .env: %s", env_path)
    except Exception as e:
        logger.exception("写入 .env 失败")
        raise HTTPException(status_code=500, detail=f"写入 .env 失败: {e}")

    # Check if any changed key requires restart
    requires_restart = any(
        k in {
            "LLM_MODEL", "LLM_BASE_URL", "SNAPSHOT_SOURCE_PRIORITY",
            "TUSHARE_API_URL", "DSA_API_URL", "ALPHASIFT_DATA_DIR",
            "POST_ANALYZERS",
        }
        for k in changed_keys
    )

    return {
        "status": "ok",
        "updated": changed_keys,
        "requires_restart": requires_restart,
        "message": "部分变量需要重启后端才能生效" if requires_restart else "已生效（部分变量下次请求生效）",
    }


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
        sources = getattr(config, "snapshot_source_priority", None)
        if sources:
            details["snapshot_sources"] = list(sources)
        else:
            details["snapshot_sources"] = "未配置"
    except Exception as e:
        details["snapshot_sources"] = f"读取失败: {e}"

    # LLM 配置状态
    llm_model = getattr(config, "llm_model", None) or getattr(config, "default_llm_model", None)
    details["llm_model"] = llm_model or "未配置"
    details["llm_status"] = "已配置" if llm_model else "未配置"

    # DSA 连通性
    dsa_url = getattr(config, "dsa_api_url", None) or ""
    details["dsa_url"] = dsa_url or "未配置"

    dsa_reachable = False
    if dsa_url:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{dsa_url.rstrip('/')}/api/health")
                dsa_reachable = resp.status_code < 500
        except Exception:
            dsa_reachable = False
    details["dsa_reachable"] = dsa_reachable

    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
        details=details,
    )
