"""Unit tests for `SqliteLifecycleSink`: insert, query, retention, schema
versioning, idempotent close, in-memory mode for tests, tuple field
round-trip.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from arc_guard_core.lifecycle import (
    FindingProduced,
    LifecycleSink,
    RequestStarted,
    new_event_id,
)

from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink


def _request_started(rid: str, seq: int = 0) -> RequestStarted:
    return RequestStarted(
        id=new_event_id(),
        parent_id=None,
        seq=seq,
        ts=datetime.now(UTC),
        rid=rid,
        route="/v1/chat/completions",
        model="echo",
        msg_count=1,
        input_size_bytes=42,
    )


def _finding(rid: str, parent_id: str, seq: int = 1) -> FindingProduced:
    return FindingProduced(
        id=new_event_id(),
        parent_id=parent_id,
        seq=seq,
        ts=datetime.now(UTC),
        rid=rid,
        entity_type="EMAIL_ADDRESS",
        span=(12, 29),
        score=1.0,
        risk_level=3,
        inspector="presidio",
    )


def test_satisfies_lifecycle_sink_protocol() -> None:
    sink = SqliteLifecycleSink(":memory:")
    assert isinstance(sink, LifecycleSink)


def test_emit_and_query_round_trip_in_memory() -> None:
    sink = SqliteLifecycleSink(":memory:")
    rs = _request_started("rid-1")
    fp = _finding("rid-1", parent_id=rs.id, seq=1)

    asyncio.run(sink.emit(rs))
    asyncio.run(sink.emit(fp))

    result = asyncio.run(sink.query("rid-1"))
    assert result is not None
    assert len(result) == 2
    assert result[0].seq == 0
    assert result[1].seq == 1
    # tuple fields round-trip as tuples (not lists)
    assert isinstance(result[1].span, tuple)
    assert result[1].span == (12, 29)


def test_query_unknown_rid_returns_none() -> None:
    sink = SqliteLifecycleSink(":memory:")
    assert asyncio.run(sink.query("never-seen")) is None


def test_event_id_collision_is_silently_dropped() -> None:
    """`INSERT OR IGNORE` means re-emitting an event with the same id is a
    no-op rather than raising IntegrityError. (Useful when sinks fan out
    and one delivers twice.)"""
    sink = SqliteLifecycleSink(":memory:")
    rs = _request_started("rid-dup")
    asyncio.run(sink.emit(rs))
    asyncio.run(sink.emit(rs))  # exact same id; should be no-op
    result = asyncio.run(sink.query("rid-dup"))
    assert result is not None and len(result) == 1


def test_persists_across_construction_when_file_backed(tmp_path: Path) -> None:
    """Restart-survivability: write through one sink instance, close it,
    open a fresh sink against the same file, query the rid back."""
    db = tmp_path / "lifecycle.db"

    sink1 = SqliteLifecycleSink(str(db))
    rs = _request_started("persistent-rid")
    asyncio.run(sink1.emit(rs))
    asyncio.run(sink1.close())

    sink2 = SqliteLifecycleSink(str(db))
    result = asyncio.run(sink2.query("persistent-rid"))
    asyncio.run(sink2.close())
    assert result is not None
    assert len(result) == 1
    assert result[0].rid == "persistent-rid"


def test_schema_version_set_to_2_on_first_open(tmp_path: Path) -> None:
    """Schema is at v2 after the dashboard-data-plane migration. The
    forward-only migration adds three new tables and upserts the meta row;
    re-opening preserves v2 without duplicating the row."""
    db = tmp_path / "lc.db"
    sink = SqliteLifecycleSink(str(db))
    assert sink.schema_version == "2"
    asyncio.run(sink.close())

    sink2 = SqliteLifecycleSink(str(db))
    assert sink2.schema_version == "2"
    asyncio.run(sink2.close())


def test_retention_deletes_rows_beyond_max_rows(tmp_path: Path) -> None:
    db = tmp_path / "lc.db"
    sink = SqliteLifecycleSink(str(db), max_rows=5, max_age_days=365)
    # Emit 12 events (which all share a rid for simplicity).
    for i in range(12):
        ev = _request_started(f"rid-{i}", seq=i)
        asyncio.run(sink.emit(ev))
    assert len(sink) == 12

    deleted = sink._run_cleanup_once()
    # Only 5 most-recent rows should remain; 7 should have been deleted.
    assert deleted == 7
    assert len(sink) == 5

    asyncio.run(sink.close())


def test_retention_deletes_rows_older_than_max_age(tmp_path: Path) -> None:
    db = tmp_path / "lc.db"
    sink = SqliteLifecycleSink(str(db), max_rows=1_000_000, max_age_days=1)
    # Emit one event, then manually backdate its created_at to 2 days ago.
    rs = _request_started("old-rid")
    asyncio.run(sink.emit(rs))
    two_days_ago = (datetime.now(UTC) - timedelta(days=2)).timestamp()
    sink._conn.execute(
        "UPDATE lifecycle_events SET created_at = ? WHERE id = ?",
        (two_days_ago, rs.id),
    )

    deleted = sink._run_cleanup_once()
    assert deleted == 1
    assert asyncio.run(sink.query("old-rid")) is None

    asyncio.run(sink.close())


def test_close_is_idempotent_and_silent() -> None:
    sink = SqliteLifecycleSink(":memory:")
    asyncio.run(sink.close())
    asyncio.run(sink.close())  # second call must not raise


def test_emit_after_close_is_no_op() -> None:
    sink = SqliteLifecycleSink(":memory:")
    asyncio.run(sink.close())
    # Should not raise; should silently skip.
    asyncio.run(sink.emit(_request_started("after-close")))


def test_invalid_constructor_args_raise() -> None:
    with pytest.raises(ValueError):
        SqliteLifecycleSink(":memory:", max_rows=0)
    with pytest.raises(ValueError):
        SqliteLifecycleSink(":memory:", max_age_days=0)
    with pytest.raises(ValueError):
        SqliteLifecycleSink(":memory:", cleanup_interval_seconds=0)
