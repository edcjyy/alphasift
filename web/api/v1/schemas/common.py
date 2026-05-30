# -*- coding: utf-8 -*-
"""AlphaSift Web API — Pydantic 请求/响应模型定义。"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ==============================================================================
# 选股 Screen
# ==============================================================================

class ScreenRequest(BaseModel):
    """选股请求参数。"""
    strategy: str = Field(..., description="策略名称，例如 default / aggressive")
    max_output: int | None = Field(default=None, ge=1, description="最大输出股票数量")
    use_llm: bool = Field(default=True, description="是否启用 LLM 分析")
    daily_enrich: bool = Field(default=False, description="是否批量补充每日行情数据")
    post_analyzers: list[str] | None = Field(default=None, description="后置分析器列表")
    save_run: bool = Field(default=False, description="是否将本次运行结果保存到本地")
    explain: bool = Field(default=False, description="是否生成 LLM 解释")
    context: str = Field(default="", description="用户额外上下文描述")
    context_files: list[str] | None = Field(default=None, description="上下文文件路径列表")
    candidate_context_files: list[str] | None = Field(default=None, description="候选上下文文件路径列表")
    collect_candidate_context: bool = Field(default=False, description="是否收集候选股上下文")
    candidate_context_max_candidates: int | None = Field(default=None, ge=1, description="候选上下文最大候选数")
    candidate_context_providers: list[str] | None = Field(default=None, description="候选上下文数据源")
    candidate_context_news_limit: int = Field(default=3, ge=0, description="每只候选股新闻条数上限")
    candidate_context_announcement_limit: int = Field(default=3, ge=0, description="每只候选股公告条数上限")
    deep_analysis: bool = Field(default=False, description="是否启用 DSA 深度后置分析")


class ScreenResponse(BaseModel):
    """选股结果（JSON 兜底序列化）。"""
    run_id: str | None = Field(default=None, description="保存后的运行 ID")
    result: dict = Field(..., description="ScreenResult 的字典序列化结果")
    task_id: str | None = Field(default=None, description="任务ID，用于轮询进度")


# ==============================================================================
# 运行记录 Runs
# ==============================================================================

class RunSummary(BaseModel):
    """历史运行记录摘要。"""
    run_id: str
    strategy: str
    created_at: str
    picks_count: int
    snapshot_source: str | None = None


class RunDetail(BaseModel):
    """单次运行记录的完整数据。"""
    run_id: str
    result: dict = Field(..., description="ScreenResult 完整数据")


# ==============================================================================
# 评估 Evaluate
# ==============================================================================

class EvaluateRequest(BaseModel):
    """T+N 评估请求参数。"""
    explain: bool = Field(default=False, description="是否产出 LLM 解释")
    with_price_path: bool = Field(default=False, description="是否附带价格走势数据")


class EvaluateResponse(BaseModel):
    """T+N 评估结果。"""
    run_id: str
    result: dict = Field(..., description="EvaluationResult 完整数据")


# ==============================================================================
# 策略 Strategies
# ==============================================================================

class StrategySummary(BaseModel):
    """可用策略摘要。"""
    name: str
    display_name: str | None = None
    description: str | None = None
    version: str | None = None
    category: str | None = None
    tags: list[str] | None = None


# ==============================================================================
# 系统 System
# ==============================================================================

class HealthResponse(BaseModel):
    """系统健康状态。"""
    status: str = "ok"
    timestamp: str
    details: dict = Field(default_factory=dict, description="子系统状态详情")
