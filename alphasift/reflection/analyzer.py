# -*- coding: utf-8 -*-
"""Reflection Analyzer — LLM-based evaluation diagnosis and change proposal."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from alphasift.reflection.models import ReflectionResult, StrategyChange

logger = logging.getLogger(__name__)

# Prompt template for the analyzer
_ANALYZER_SYSTEM_PROMPT = """你是一位量化策略研究员。你的任务是分析选股策略的 T+N 回测评估结果，诊断问题并提出具体的参数修改建议。

## 输出格式
你必须输出一个严格的 JSON 对象，格式如下：
```json
{
  "diagnosis": "对策略表现的中文诊断分析（100-200字）",
  "summary": "一句话总结（20字以内）",
  "changes": [
    {
      "change_type": "ADJUST_WEIGHT | MODIFY_FILTER | UPDATE_REGIME | MODIFY_SCORECARD | MODIFY_RISK",
      "target": "factor_weights.momentum | hard_filters.pe_ttm_max | regime_weights.bearish.filter_mult.change_pct_max 等",
      "old_value": "当前值",
      "new_value": "建议值",
      "reason": "修改理由（10-20字）",
      "confidence": 0.7
    }
  ]
}
```

## 修改类型说明
- ADJUST_WEIGHT: 调整 factor_weights 中的因子权重
- MODIFY_FILTER: 修改 hard_filters 中的筛选条件
- UPDATE_REGIME: 修改 regime_weights 中的参数
- MODIFY_SCORECARD: 修改 scorecard_profile
- MODIFY_RISK: 修改 risk_profile

## 策略参数修改原则
1. 变动不超过 30%（乘数范围 0.7-1.3）
2. 每次最多 3 个修改
3. 修改必须有明确的因果逻辑
4. 估值类策略不轻易提高 PE 上限
5. 动量类策略不轻易降低 activity 权重
6. 熊市 regime 优先收紧风险参数

## 分析维度
1. 胜率：检查是否因为硬筛选太宽/太窄
2. 收益率：检查因子权重是否偏离市场风格
3. 最大回撤：检查风险参数是否过于宽松
4. 行业集中度：检查组合是否过于集中在某个板块
5. 选股数量：检查硬筛选是否会选出过多/过少的票"""


def _build_analysis_prompt(
    strategy_name: str,
    strategy_yaml: str,
    win_rate: float | None,
    avg_return_pct: float | None,
    elapsed_days: int | None,
    win_count: int,
    loss_count: int,
    pick_count: int,
    winners: list[dict],
    losers: list[dict],
) -> str:
    """Build the LLM prompt for strategy analysis."""

    winners_str = "\n".join(
        f"  - {w['name']}({w['code']}): 收益率 {w['return_pct']:+.1f}%, "
        f"行业 {w.get('sector','?')}, 评分 {w.get('score','?')}"
        for w in winners[:5]
    ) if winners else "  (无)"

    losers_str = "\n".join(
        f"  - {l['name']}({l['code']}): 收益率 {l['return_pct']:+.1f}%, "
        f"行业 {l.get('sector','?')}, 评分 {l.get('score','?')}"
        for l in losers[:5]
    ) if losers else "  (无)"

    return f"""## 策略信息
策略名称: {strategy_name}
评估周期: {elapsed_days or '?'} 天

## 评估结果
- 总选股数: {pick_count}
- 盈利: {win_count} 只, 亏损: {loss_count} 只
- 胜率: {(win_rate or 0) * 100:.1f}%
- 平均收益率: {avg_return_pct or 0:+.2f}%

## 表现最好的选股
{winners_str}

## 表现最差的选股
{losers_str}

## 当前策略 YAML
```yaml
{strategy_yaml}
```

请基于以上信息，诊断该策略的问题并提出具体的参数修改建议。输出 JSON。"""


def analyze_evaluation(
    *,
    strategy_name: str,
    strategy_yaml: str,
    win_rate: float | None = None,
    avg_return_pct: float | None = None,
    elapsed_days: int | None = None,
    win_count: int = 0,
    loss_count: int = 0,
    pick_count: int = 0,
    winners: list[dict] | None = None,
    losers: list[dict] | None = None,
    model: str | None = None,
) -> ReflectionResult:
    """Analyze an evaluation result using LLM and propose strategy changes.

    Returns a ReflectionResult with diagnosis and change proposals.
    """
    try:
        from litellm import completion
    except ImportError:
        logger.error("litellm not installed — cannot run reflection analysis")
        return ReflectionResult(
            run_id="",
            strategy=strategy_name,
            evaluated_at="",
            diagnosis="litellm 未安装，无法进行分析",
            summary="依赖缺失",
        )

    # Determine model
    if model is None:
        from alphasift.config import Config
        config = Config.from_env()
        model = config.llm_model or "openai/gpt-4o-mini"

    # Build prompt
    user_prompt = _build_analysis_prompt(
        strategy_name=strategy_name,
        strategy_yaml=strategy_yaml,
        win_rate=win_rate,
        avg_return_pct=avg_return_pct,
        elapsed_days=elapsed_days,
        win_count=win_count,
        loss_count=loss_count,
        pick_count=pick_count,
        winners=winners or [],
        losers=losers or [],
    )

    logger.info("Requesting reflection analysis: strategy=%s model=%s", strategy_name, model)

    response = completion(
        model=model,
        messages=[
            {"role": "system", "content": _ANALYZER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    raw = response.choices[0].message.content or ""
    logger.debug("LLM raw response: %s", raw[:500])

    # Parse JSON from response (may be wrapped in ```json ... ```)
    json_str = raw
    if "```json" in raw:
        match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
        if match:
            json_str = match.group(1)
    elif "```" in raw:
        match = re.search(r"```\s*(.*?)\s*```", raw, re.DOTALL)
        if match:
            json_str = match.group(1)

    try:
        data = json.loads(json_str.strip())
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM JSON response, using raw text as diagnosis")
        return ReflectionResult(
            run_id="",
            strategy=strategy_name,
            evaluated_at="",
            diagnosis=raw[:500],
            summary="LLM 输出解析失败",
            model_used=model,
            raw_response=raw,
        )

    # Parse changes
    changes = []
    for c in data.get("changes", []):
        changes.append(StrategyChange(
            change_type=c.get("change_type", "?"),
            target=c.get("target", "?"),
            old_value=str(c.get("old_value", "?")),
            new_value=str(c.get("new_value", "?")),
            reason=c.get("reason", "无说明"),
            confidence=float(c.get("confidence", 0.5)),
        ))

    return ReflectionResult(
        run_id="",
        strategy=strategy_name,
        evaluated_at="",
        diagnosis=data.get("diagnosis", raw[:300]),
        summary=data.get("summary", ""),
        changes=changes,
        win_rate=win_rate,
        avg_return_pct=avg_return_pct,
        elapsed_days=elapsed_days,
        pick_count=pick_count,
        win_count=win_count,
        loss_count=loss_count,
        model_used=model,
        raw_response=raw,
    )
