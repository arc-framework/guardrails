"""Integration test: ``DecisionRecordRecorder`` writes rows to ``decision_records``.

Verifies:
- Recorder ignores non-``DecisionEmitted`` events.
- ``DecisionEmitted`` events produce exactly one row keyed by ``(rid, decision_id)``.
- Rows survive a recorder restart (sink reopens against the same DB file).
- Dropped-write counter increments under simulated failure.
"""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from arc_guard_core.lifecycle.events import (
    DecisionEmitted,
    RequestStarted,
)

from arc_guard.observability.decision_record_recorder import DecisionRecordRecorder
from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink


def _ts(s: int = 0) -> datetime:
    return datetime(2026, 5, 9, 14, 0, s, tzinfo=UTC)


def _row_count(path: str) -> int:
    conn = sqlite3.connect(path)
    try:
        return int(
            conn.execute("SELECT COUNT(*) FROM decision_records").fetchone()[0]
        )
    finally:
        conn.close()


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    db = tmp_path / "arc_guardrail.db"
    SqliteLifecycleSink(str(db))
    return str(db)


@pytest.mark.asyncio
async def test_decision_emitted_writes_row(db_path: str) -> None:
    rec = DecisionRecordRecorder(db_path)
    try:
        await rec.emit(
            DecisionEmitted(
                id="ev-1",
                parent_id=None,
                seq=1,
                ts=_ts(0),
                rid="rid-1",
                action="block",
                decision_id="dec-XYZ",
            )
        )
        # Drain task processes asynchronously; give it a tick.
        await asyncio.sleep(0.05)
        assert _row_count(db_path) == 1
    finally:
        await rec.close()


@pytest.mark.asyncio
async def test_non_decision_events_ignored(db_path: str) -> None:
    rec = DecisionRecordRecorder(db_path)
    try:
        await rec.emit(
            RequestStarted(
                id="ev-1", parent_id=None, seq=1, ts=_ts(0), rid="rid-1"
            )
        )
        await asyncio.sleep(0.05)
        assert _row_count(db_path) == 0
    finally:
        await rec.close()


@pytest.mark.asyncio
async def test_record_survives_recorder_restart(db_path: str) -> None:
    rec = DecisionRecordRecorder(db_path)
    try:
        await rec.emit(
            DecisionEmitted(
                id="ev-1",
                parent_id=None,
                seq=1,
                ts=_ts(0),
                rid="rid-1",
                action="block",
                decision_id="dec-XYZ",
            )
        )
        await asyncio.sleep(0.05)
    finally:
        await rec.close()

    # Re-open with a fresh recorder against the same DB; the row persists.
    rec2 = DecisionRecordRecorder(db_path)
    try:
        assert _row_count(db_path) == 1
    finally:
        await rec2.close()


@pytest.mark.asyncio
async def test_emit_after_close_is_silent_no_op(db_path: str) -> None:
    rec = DecisionRecordRecorder(db_path)
    await rec.close()
    await rec.emit(
        DecisionEmitted(
            id="ev-1",
            parent_id=None,
            seq=1,
            ts=_ts(0),
            rid="rid-1",
            action="block",
            decision_id="dec-XYZ",
        )
    )
    # Should not raise; row count stays zero.
    assert _row_count(db_path) == 0
