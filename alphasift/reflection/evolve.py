# -*- coding: utf-8 -*-
"""Evolution orchestrator — multi-round reflection + LLM self-critic."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from alphasift.reflection.critic import CriticResult, validate_changes
from alphasift.reflection.models import ReflectionResult, StrategyChange

logger = logging.getLogger(__name__)

_SELF_CRITIC_PROMPT = """你是一位资深量化策略审查员。请审核以下 LLM 提出的策略修改建议。

策略类型: {category}
策略名称: {strategy}

当前修改建议（已通过规则审查）:
{changes_text}

请判断每个修改:
1. 方向是否正确（该加还是该减）
2. 幅度是否合适（过大/过小/正好）
3. 是否有交互冲突（多个修改之间）

输出 JSON:
```json
{{
  "verdict": "approve | adjust | reject",
  "adjustments": [
    {{"target": "...", "new_value": "...", "reason": "..."}}
  ],
  "overall_comment": "..."
}}
```"""


def llm_self_critic(
    changes: list[StrategyChange],
    *,
    strategy_name: str,
    strategy_category: str,
    model: str | None = None,
) -> tuple[list[StrategyChange], str]:
    """LLM second-pass validation of proposed changes.

    Returns (adjusted_changes, comment).
    """
    if not changes:
        return changes, "无修改可审查"

    try:
        from litellm import completion
    except ImportError:
        return changes, "litellm 未安装，跳过 LLM 审查"

    from alphasift.config import Config
    config = Config.from_env()
    model = model or config.llm_model or "openai/gpt-4o-mini"

    changes_text = "\n".join(
        f"  {i+1}. [{c.change_type}] {c.target}: {c.old_value} → {c.new_value} [{c.reason}]"
        for i, c in enumerate(changes)
    )

    prompt = _SELF_CRITIC_PROMPT.format(
        category=strategy_category, strategy=strategy_name, changes_text=changes_text,
    )

    response = completion(
        model=model,
        messages=[
            {"role": "system", "content": "你是一位审慎的量化策略审查员。只输出 JSON。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=800,
    )

    raw = response.choices[0].message.content or ""
    json_str = raw
    if "```json" in raw:
        m = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
        if m:
            json_str = m.group(1)

    try:
        data = json.loads(json_str.strip())
    except json.JSONDecodeError:
        return changes, f"LLM 审查解析失败: {raw[:200]}"

    verdict = data.get("verdict", "approve")
    comment = data.get("overall_comment", "")

    if verdict == "reject":
        return [], f"LLM 审查拒绝: {comment}"

    if verdict == "adjust":
        adjustments = {a["target"]: a.get("new_value") for a in data.get("adjustments", [])}
        for c in changes:
            if c.target in adjustments and adjustments[c.target]:
                c.new_value = str(adjustments[c.target])
        return changes, f"LLM 审查调整: {comment}"

    return changes, f"LLM 审查通过: {comment}"


def evolve_multi_round(
    *,
    run_id: str,
    data_dir: Path | None = None,
    strategy_dir: Path | None = None,
    max_rounds: int = 3,
    min_confidence: float = 0.5,
    min_critic_score: float = 0.6,
    model: str | None = None,
    use_llm_critic: bool = True,
) -> list[ReflectionResult]:
    """Multi-round auto-evolution loop.

    Each round: reflect → (LLM critic) → apply → re-evaluate → repeat if improved.

    Args:
        max_rounds: Maximum number of evolution rounds
        min_confidence: Minimum LLM confidence for changes
        min_critic_score: Minimum critic score to proceed to next round
        use_llm_critic: Enable LLM self-critic pass

    Returns:
        List of ReflectionResult, one per round.
    """
    from alphasift.config import Config
    from alphasift.reflection import reflect_on_evaluation

    config = Config.from_env()
    data_dir = data_dir or config.data_dir
    strategy_dir = strategy_dir or config.strategies_dir

    results: list[ReflectionResult] = []
    current_run_id = run_id

    for round_num in range(1, max_rounds + 1):
        logger.info("=== Evolution Round %d/%d (run=%s) ===", round_num, max_rounds, current_run_id)

        # 1. Reflect
        result = reflect_on_evaluation(
            run_id=current_run_id,
            data_dir=data_dir,
            strategy_dir=strategy_dir,
            model=model,
            apply=False,
            min_confidence=min_confidence,
        )
        results.append(result)

        if not result.changes:
            logger.info("Round %d: no changes proposed, stopping", round_num)
            break

        # 2. LLM self-critic
        if use_llm_critic and result.changes:
            category = "framework"
            yaml_path = strategy_dir / f"{result.strategy}.yaml"
            if yaml_path.exists():
                import yaml
                try:
                    d = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
                    category = d.get("category", "framework") if isinstance(d, dict) else "framework"
                except Exception:
                    pass

            adjusted, llm_comment = llm_self_critic(
                result.changes,
                strategy_name=result.strategy,
                strategy_category=category,
                model=model,
            )
            result.changes = adjusted
            result.diagnosis += f"\n\n[LLM 审查] {llm_comment}"

        # 3. Rule-based critic
        critic = validate_changes(
            result.changes,
            strategy_category="framework",
            strategy_name=result.strategy,
            min_confidence=min_confidence,
        )

        if critic.score < min_critic_score or not critic.passed:
            logger.info("Round %d: critic score %.2f < %.2f, stopping", round_num, critic.score, min_critic_score)
            break

        # 4. Apply + re-evaluate
        result2 = reflect_on_evaluation(
            run_id=current_run_id,
            data_dir=data_dir,
            strategy_dir=strategy_dir,
            model=model,
            apply=True,
            min_confidence=min_confidence,
            auto_reevaluate=True,
        )
        results.append(result2)

        # After auto-reevaluate, find the latest evaluation run for the
        # next round.  reflect_on_evaluation creates a new screen/eval run
        # internally (apply=True + auto_reevaluate=True) but only returns
        # the ReflectionResult for the *original* run_id, so we scan the
        # data directory for the most recent run to use in the next round.
        import uuid as _uuid
        evals_dir = data_dir / "evaluations"
        runs_dir = data_dir / "runs"
        next_run_id = current_run_id
        try:
            if evals_dir.is_dir():
                eval_files = sorted(
                    evals_dir.glob("*.json"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if eval_files:
                    next_run_id = eval_files[0].stem
        except Exception:
            pass  # keep current_run_id on failure
        current_run_id = next_run_id

    return results
