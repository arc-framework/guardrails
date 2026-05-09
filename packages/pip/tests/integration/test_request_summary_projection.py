"""Integration test: ``RequestSummaryProjector`` populates ``request_summaries``.

Drives synthetic ``LifecycleEvent`` instances through the projector and
asserts the row content matches the documented projection rules:
- RequestStarted → row inserted with status='live', live=1
- StageRan → stage column updated
- FindingProduced → max_risk takes the running maximum
- DecisionEmitted → decision_id + final_action populated
- RefusalProduced → refusal_code populated
- RequestCompleted → status='completed', live=0, duration_ms set
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from arc_guard_core.lifecycle.events import (
    DecisionEmitted,
    FindingProduced,
    RefusalProduced,
    RequestCompleted,
    RequestStarted,
    StageRan,
)

from arc_guard.observability.request_summary_projector import (
    RequestSummaryProjector,
)
from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink


def _row(path: str, rid: str) -> sqlite3.Row | None:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM request_summaries WHERE rid = ?", (rid,)
        ).fetchone()
    finally:
        conn.close()


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    db = tmp_path / "arc_guardrail.db"
    SqliteLifecycleSink(str(db))  # run migration v2
    return str(db)


def _ts(seconds: int = 0) -> datetime:
    return datetime(2026, 5, 9, 12, 0, seconds, tzinfo=UTC)


@pytest.mark.asyncio
async def test_request_started_inserts_live_row(db_path: str) -> None:
    p = RequestSummaryProjector(db_path)
    try:
        await p.emit(
            RequestStarted(
                id="ev-001", parent_id=None, seq=1, ts=_ts(0), rid="rid-1"
            )
        )
        row = _row(db_path, "rid-1")
        assert row is not None
        assert row["status"] == "live"
        assert row["live"] == 1
        assert row["started_at"] == _ts(0).isoformat()
    finally:
        await p.close()


@pytest.mark.asyncio
async def test_stage_ran_updates_stage(db_path: str) -> None:
    p = RequestSummaryProjector(db_path)
    try:
        await p.emit(
            RequestStarted(
                id="ev-001", parent_id=None, seq=1, ts=_ts(0), rid="rid-1"
            )
        )
        await p.emit(
            StageRan(
                id="ev-002",
                parent_id="ev-001",
                seq=2,
                ts=_ts(1),
                rid="rid-1",
                stage="classify",
            )
        )
        row = _row(db_path, "rid-1")
        assert row is not None
        assert row["stage"] == "classify"


    finally:
        await p.close()


@pytest.mark.asyncio
async def test_finding_produced_updates_max_risk(db_path: str) -> None:
    p = RequestSummaryProjector(db_path)
    try:
        await p.emit(
            RequestStarted(
                id="ev-001", parent_id=None, seq=1, ts=_ts(0), rid="rid-1"
            )
        )
        await p.emit(
            FindingProduced(
                id="ev-002",
                parent_id="ev-001",
                seq=2,
                ts=_ts(1),
                rid="rid-1",
                score=0.4,
            )
        )
        await p.emit(
            FindingProduced(
                id="ev-003",
                parent_id="ev-001",
                seq=3,
                ts=_ts(2),
                rid="rid-1",
                score=0.9,
            )
        )
        await p.emit(
            FindingProduced(
                id="ev-004",
                parent_id="ev-001",
                seq=4,
                ts=_ts(3),
                rid="rid-1",
                score=0.2,
            )
        )
        row = _row(db_path, "rid-1")
        assert row is not None
        assert row["max_risk"] == pytest.approx(0.9)
    finally:
        await p.close()


@pytest.mark.asyncio
async def test_decision_emitted_populates_id_and_action(db_path: str) -> None:
    p = RequestSummaryProjector(db_path)
    try:
        await p.emit(
            RequestStarted(
                id="ev-001", parent_id=None, seq=1, ts=_ts(0), rid="rid-1"
            )
        )
        await p.emit(
            DecisionEmitted(
                id="ev-002",
                parent_id="ev-001",
                seq=2,
                ts=_ts(1),
                rid="rid-1",
                action="block",
                decision_id="dec-XYZ",
            )
        )
        row = _row(db_path, "rid-1")
        assert row["decision_id"] == "dec-XYZ"
        assert row["final_action"] == "block"
    finally:
        await p.close()


@pytest.mark.asyncio
async def test_refusal_produced_sets_refusal_code(db_path: str) -> None:
    p = RequestSummaryProjector(db_path)
    try:
        await p.emit(
            RequestStarted(
                id="ev-001", parent_id=None, seq=1, ts=_ts(0), rid="rid-1"
            )
        )
        await p.emit(
            RefusalProduced(
                id="ev-002",
                parent_id="ev-001",
                seq=2,
                ts=_ts(1),
                rid="rid-1",
                refusal_code="PII_LEAK",
                decision_id="dec-XYZ",
            )
        )
        row = _row(db_path, "rid-1")
        assert row["refusal_code"] == "PII_LEAK"
    finally:
        await p.close()


@pytest.mark.asyncio
async def test_request_completed_flips_live_and_sets_duration(
    db_path: str,
) -> None:
    p = RequestSummaryProjector(db_path)
    try:
        await p.emit(
            RequestStarted(
                id="ev-001", parent_id=None, seq=1, ts=_ts(0), rid="rid-1"
            )
        )
        await p.emit(
            RequestCompleted(
                id="ev-002",
                parent_id="ev-001",
                seq=2,
                ts=_ts(1),
                rid="rid-1",
                blocked=False,
                pre_action="pass",
                total_duration_ms=842.5,
            )
        )
        row = _row(db_path, "rid-1")
        assert row["status"] == "completed"
        assert row["live"] == 0
        assert row["duration_ms"] == 842
    finally:
        await p.close()


@pytest.mark.asyncio
async def test_blocked_request_completed_sets_block_action(
    db_path: str,
) -> None:
    p = RequestSummaryProjector(db_path)
    try:
        await p.emit(
            RequestStarted(
                id="ev-001", parent_id=None, seq=1, ts=_ts(0), rid="rid-1"
            )
        )
        await p.emit(
            RequestCompleted(
                id="ev-002",
                parent_id="ev-001",
                seq=2,
                ts=_ts(1),
                rid="rid-1",
                blocked=True,
                pre_action="pass",
                total_duration_ms=10.0,
            )
        )
        row = _row(db_path, "rid-1")
        # COALESCE preserves existing final_action; for a fresh row with NULL,
        # it falls back to the computed 'block' label.
        assert row["final_action"] == "block"
    finally:
        await p.close()


@pytest.mark.asyncio
async def test_dropped_writes_counter_initially_zero(db_path: str) -> None:
    p = RequestSummaryProjector(db_path)
    try:
        assert p.dropped_writes == 0
    finally:
        await p.close()
