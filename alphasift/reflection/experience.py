# -*- coding: utf-8 -*-
"""Reflection Experience Store — SQLite-backed evolution history.

Records every reflection round: what was changed, whether it improved the strategy,
and what lessons were learned. Used by the meta-learner to discover optimal
evolution patterns.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from alphasift.reflection.models import ReflectionResult, StrategyChange

logger = logging.getLogger(__name__)
_TZ_SHANGHAI = timezone(timedelta(hours=8))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS evolution_records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy    TEXT    NOT NULL,
    run_id      TEXT    NOT NULL,
    category    TEXT    DEFAULT 'framework',
    timestamp   TEXT    NOT NULL,
    -- Before state
    win_rate_before       REAL,
    avg_return_before     REAL,
    pick_count_before     INTEGER,
    -- Diagnosis
    diagnosis   TEXT,
    summary     TEXT,
    model_used  TEXT,
    -- Changes applied (JSON array of StrategyChange)
    changes_json TEXT,
    passed_count INTEGER DEFAULT 0,
    rejected_count INTEGER DEFAULT 0,
    critic_score REAL DEFAULT 1.0,
    -- Outcome (filled later after re-evaluation)
    after_run_id TEXT,
    win_rate_after        REAL,
    avg_return_after      REAL,
    improved     INTEGER,  -- 1=yes, 0=no, NULL=not yet evaluated
    -- Meta
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_strategy ON evolution_records(strategy);
CREATE INDEX IF NOT EXISTS idx_run_id ON evolution_records(run_id);
CREATE INDEX IF NOT EXISTS idx_improved ON evolution_records(improved);
"""


def _get_db_path(data_dir: Path | str) -> Path:
    """Get the SQLite database path."""
    if isinstance(data_dir, str):
        data_dir = Path(data_dir)
    db_path = data_dir / ".reflection.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def _now() -> str:
    return datetime.now(_TZ_SHANGHAI).isoformat()


def init_db(data_dir: Path) -> sqlite3.Connection:
    """Initialize the experience database."""
    db_path = _get_db_path(data_dir)
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA)
    conn.commit()
    logger.info("Experience DB initialized: %s", db_path)
    return conn


def save_reflection(
    result: ReflectionResult,
    *,
    data_dir: Path,
    strategy_category: str = "framework",
    critic_score: float = 1.0,
    passed_count: int = 0,
    rejected_count: int = 0,
) -> int:
    """Save a reflection result to the experience store.

    Returns the record ID.
    """
    conn = init_db(data_dir)
    try:
        changes_json = json.dumps(
            [
                {
                    "change_type": c.change_type,
                    "target": c.target,
                    "old_value": c.old_value,
                    "new_value": c.new_value,
                    "reason": c.reason,
                    "confidence": c.confidence,
                }
                for c in result.changes
            ],
            ensure_ascii=False,
        )

        cursor = conn.execute(
            """INSERT INTO evolution_records
               (strategy, run_id, category, timestamp,
                win_rate_before, avg_return_before, pick_count_before,
                diagnosis, summary, model_used,
                changes_json, passed_count, rejected_count, critic_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.strategy,
                result.run_id,
                strategy_category,
                result.reflected_at or _now(),
                result.win_rate,
                result.avg_return_pct,
                result.pick_count,
                result.diagnosis,
                result.summary,
                result.model_used,
                changes_json,
                passed_count,
                rejected_count,
                critic_score,
            ),
        )
        conn.commit()
        record_id = cursor.lastrowid or 0
        logger.info("Reflection saved: id=%d strategy=%s", record_id, result.strategy)
        return record_id
    finally:
        conn.close()


def update_outcome(
    record_id: int,
    *,
    data_dir: Path,
    after_run_id: str = "",
    win_rate_after: float | None = None,
    avg_return_after: float | None = None,
    improved: bool | None = None,
) -> bool:
    """Update the outcome of a reflection after re-evaluation."""
    conn = init_db(data_dir)
    try:
        conn.execute(
            """UPDATE evolution_records
               SET after_run_id = ?,
                   win_rate_after = ?,
                   avg_return_after = ?,
                   improved = ?,
                   updated_at = ?
               WHERE id = ?""",
            (
                after_run_id,
                win_rate_after,
                avg_return_after,
                1 if improved is True else (0 if improved is False else None),
                _now(),
                record_id,
            ),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_history(
    strategy: str,
    *,
    data_dir: Path,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Get evolution history for a strategy."""
    conn = init_db(data_dir)
    try:
        cursor = conn.execute(
            """SELECT * FROM evolution_records
               WHERE strategy = ?
               ORDER BY id DESC
               LIMIT ?""",
            (strategy, limit),
        )
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()


def get_change_history(
    strategy: str,
    *,
    data_dir: Path,
    target_filter: str | None = None,
) -> dict[str, list[dict]]:
    """Get change history grouped by target key, for duplication checking.

    Returns: {target_key: [{old_value, new_value, success, timestamp}, ...]}
    """
    conn = init_db(data_dir)
    try:
        cursor = conn.execute(
            """SELECT changes_json, improved FROM evolution_records
               WHERE strategy = ?
               ORDER BY id DESC""",
            (strategy,),
        )

        history: dict[str, list[dict]] = {}
        for row in cursor:
            try:
                changes = json.loads(row[0])
                success = row[1] == 1 if row[1] is not None else None
                for c in changes:
                    target = c.get("target", "")
                    if target_filter and target_filter not in target:
                        continue
                    if target not in history:
                        history[target] = []
                    history[target].append({
                        "old_value": c.get("old_value", ""),
                        "new_value": c.get("new_value", ""),
                        "success": success,
                        "change_type": c.get("change_type", ""),
                    })
            except (json.JSONDecodeError, TypeError):
                continue

        return history
    finally:
        conn.close()


def get_all_history(
    *,
    data_dir: Path,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Get all evolution records across all strategies (for meta-learning)."""
    conn = init_db(data_dir)
    try:
        cursor = conn.execute(
            """SELECT strategy, category, changes_json, improved,
                      win_rate_before, avg_return_before,
                      win_rate_after, avg_return_after,
                      passed_count, rejected_count
               FROM evolution_records
               ORDER BY id DESC
               LIMIT ?""",
            (limit,),
        )
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()
