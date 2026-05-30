# -*- coding: utf-8 -*-
"""Resumable pipeline checkpoints — lightweight persistence between stages.

Each screen() run saves intermediate DataFrames as pickle files under
``{ALPHASIFT_DATA_DIR}/checkpoints/{run_id}/``.  On restart, the pipeline
reads the newest valid checkpoint and skips already-completed stages.

Validity is gated by four conditions:
  1. Same trading day (stale snapshot from yesterday is dangerous)
  2. Data freshness (intraday snapshot ages out after SNAPSHOT_TTL_MIN)
  3. Strategy YAML unchanged (SHA256 comparison)
  4. Snapshot source unchanged (efinance vs akshare have different PE/PB)
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stage definitions — each stage produces one checkpoint file
# ---------------------------------------------------------------------------
STAGE_NAMES = [
    "01_snapshot",       # raw snapshot DataFrame (before any filter)
    "02_filtered",       # after L1 hard filter (snapshot fields only)
    "03_daily",          # after daily K-line enrichment
    "04_roe",            # after ROE enrichment
    "05_scored",         # after compute_screen_scores
]

# TTL (time-to-live) per stage — how long a checkpoint remains valid.
# Intraday data ages quickly; end-of-day data lasts until next trading day.
_SNAPSHOT_TTL_MIN = 5        # 5 minutes for real-time snapshot
_DAILY_TTL_HOURS = 6         # daily K-line data is valid all afternoon
_FINANCIAL_TTL_HOURS = 24    # ROE / fundamental data changes daily
_SCORED_TTL_MIN = 5          # depends on snapshot freshness

STAGE_TTL = {
    "01_snapshot":  timedelta(minutes=_SNAPSHOT_TTL_MIN),
    "02_filtered": timedelta(minutes=_SNAPSHOT_TTL_MIN),
    "03_daily":    timedelta(hours=_DAILY_TTL_HOURS),
    "04_roe":      timedelta(hours=_FINANCIAL_TTL_HOURS),
    "05_scored":   timedelta(minutes=_SCORED_TTL_MIN),
}


@dataclass
class CheckpointMeta:
    """Lightweight metadata stored alongside each checkpoint DataFrame."""
    stage: str
    run_id: str
    strategy: str
    created_at: str          # ISO 8601
    trade_date: str          # "2026-05-30"
    snapshot_source: str
    strategy_hash: str
    row_count: int
    columns: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_checkpoint(
    df: pd.DataFrame,
    *,
    stage: str,
    run_id: str,
    strategy: str,
    data_dir: Path,
    strategies_dir: Path,
    trade_date: str | None = None,
    snapshot_source: str = "",
) -> Path:
    """Persist a DataFrame checkpoint and its metadata."""
    cp_dir = _checkpoint_dir(run_id, data_dir)
    cp_dir.mkdir(parents=True, exist_ok=True)

    # DataFrame → Parquet
    pkl_path = cp_dir / f"{stage}.pkl"
    df.to_pickle(pkl_path)

    # Metadata → JSON
    meta = CheckpointMeta(
        stage=stage,
        run_id=run_id,
        strategy=strategy,
        created_at=datetime.now().isoformat(),
        trade_date=trade_date or _resolve_trade_date(),
        snapshot_source=snapshot_source or str(df.attrs.get("snapshot_source", "")),
        strategy_hash=_strategy_hash(strategy, strategies_dir),
        row_count=len(df),
        columns=list(df.columns),
    )
    meta_path = cp_dir / f"{stage}.json"
    meta_path.write_text(json.dumps(asdict(meta), indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info("Checkpoint saved: stage=%s rows=%d path=%s", stage, len(df), pkl_path)
    return pkl_path


def load_checkpoint(
    stage: str,
    *,
    run_id: str,
    strategy: str,
    data_dir: Path,
    strategies_dir: Path,
    snapshot_source: str = "",
) -> pd.DataFrame | None:
    """Load a valid checkpoint, or return None if missing/stale/incompatible."""
    cp_dir = _checkpoint_dir(run_id, data_dir)
    pkl_path = cp_dir / f"{stage}.pkl"
    meta_path = cp_dir / f"{stage}.json"

    if not pkl_path.exists() or not meta_path.exists():
        return None

    # Load and validate metadata
    try:
        meta_raw = json.loads(meta_path.read_text(encoding="utf-8"))
        meta = CheckpointMeta(**meta_raw)
    except Exception:
        logger.warning("Checkpoint metadata corrupt: %s", meta_path)
        return None

    valid, reason = _validate(meta, stage, strategy, strategies_dir, snapshot_source)
    if not valid:
        logger.info("Checkpoint %s invalid: %s", stage, reason)
        return None

    df = pd.read_pickle(pkl_path)
    # Carry forward snapshot attrs
    if snapshot_source and "snapshot_source" not in df.attrs:
        df.attrs["snapshot_source"] = snapshot_source
    logger.info("Checkpoint resumed: stage=%s rows=%d", stage, len(df))
    return df


def clear_checkpoints(run_id: str, data_dir: Path) -> None:
    """Remove all checkpoint files for a completed run."""
    import shutil
    cp_dir = _checkpoint_dir(run_id, data_dir)
    if cp_dir.exists():
        shutil.rmtree(cp_dir, ignore_errors=True)
        logger.debug("Checkpoints cleared: %s", cp_dir)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _checkpoint_dir(run_id: str, data_dir: Path) -> Path:
    return data_dir / "checkpoints" / run_id


def _strategy_hash(strategy: str, strategies_dir: Path) -> str:
    yaml_path = strategies_dir / f"{strategy}.yaml"
    if not yaml_path.exists():
        return "unknown"
    return hashlib.sha256(yaml_path.read_bytes()).hexdigest()[:16]


def _resolve_trade_date() -> str:
    """Best-effort A-share trading date resolution."""
    now = datetime.now()
    d = date.today()
    # Weekend → use Friday
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    # Before 15:30 on a weekday → data may not be published yet; use previous
    # trading day for end-of-day data like daily K-line.
    if d == date.today() and now.hour < 16:
        d -= timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
    return d.isoformat()


def _validate(
    meta: CheckpointMeta,
    stage: str,
    strategy: str,
    strategies_dir: Path,
    snapshot_source: str,
) -> tuple[bool, str]:
    """Return (is_valid, reason)."""
    # 1. Same trading day
    today = _resolve_trade_date()
    if meta.trade_date != today:
        return False, f"trade_date mismatch: {meta.trade_date} != {today}"

    # 2. Data freshness
    try:
        created = datetime.fromisoformat(meta.created_at)
    except ValueError:
        return False, "unparseable created_at"
    age = datetime.now() - created
    ttl = STAGE_TTL.get(stage, timedelta(minutes=5))
    if age > ttl:
        return False, f"expired: age={age}, ttl={ttl}"

    # 3. Strategy unchanged
    current_hash = _strategy_hash(strategy, strategies_dir)
    if meta.strategy_hash != current_hash:
        return False, "strategy YAML modified"

    # 4. Snapshot source consistent (only for snapshot-derived stages)
    if snapshot_source and meta.snapshot_source and stage in ("01_snapshot", "02_filtered"):
        if meta.snapshot_source != snapshot_source:
            return False, f"source mismatch: {meta.snapshot_source} != {snapshot_source}"

    # 5. Non-empty
    if meta.row_count == 0:
        return False, "empty checkpoint"

    return True, "valid"
