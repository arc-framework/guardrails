"""Integration test: retention task evicts the three new dashboard tables
in lockstep with ``lifecycle_events``.

When the retention pass identifies a set of `rid`s to evict (by age or
rowcount), the same set is removed from `request_summaries`,
`decision_records`, and `debug_entries` inside one transaction.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink


def _seed_event_for_rid(sink: SqliteLifecycleSink, rid: str, *, created_at: float) -> None:
    """Bypass emit() to insert an event row with a controlled created_at."""
    sink._conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO lifecycle_events"
        " (id, rid, seq, parent_id, event_type, event_data, created_at)"
        " VALUES (?, ?, 1, NULL, 'RequestStarted', '{}', ?)",
        (f"id-{rid}", rid, created_at),
    )


def _seed_dashboard_rows(path: str, rid: str) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "INSERT INTO request_summaries"
            " (rid, started_at, last_event_at, status, live)"
            " VALUES (?, ?, ?, 'completed', 0)",
            (rid, "2026-05-09T00:00:00+00:00", "2026-05-09T00:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO decision_records"
            " (rid, decision_id, recorded_at, payload_json, payload_size_bytes)"
            " VALUES (?, ?, ?, '{}', 2)",
            (rid, f"dec-{rid}", "2026-05-09T00:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO debug_entries"
            " (rid, seq, ts, channel, severity, message)"
            " VALUES (?, 1, ?, 'test', 'DEBUG', 'first')",
            (rid, "2026-05-09T00:00:00+00:00"),
        )
        conn.commit()
    finally:
        conn.close()


def _row_count(path: str, table: str, rid: str) -> int:
    conn = sqlite3.connect(path)
    try:
        return int(
            conn.execute(f"SELECT COUNT(*) FROM {table} WHERE rid = ?", (rid,)).fetchone()[0]
        )
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_retention_evicts_dashboard_tables_in_lockstep(
    tmp_path: Path,
) -> None:
    import time

    db = tmp_path / "arc_guardrail.db"
    sink = SqliteLifecycleSink(str(db), max_rows=1, max_age_days=365, cleanup_interval_seconds=60)
    try:
        # Seed two rids with RECENT created_at values so age-based eviction
        # doesn't fire; only the max_rows=1 check should evict rid-old.
        now = time.time()
        _seed_event_for_rid(sink, "rid-old", created_at=now - 1.0)
        _seed_event_for_rid(sink, "rid-new", created_at=now)
        _seed_dashboard_rows(str(db), "rid-old")
        _seed_dashboard_rows(str(db), "rid-new")

        # Sanity check: both rids present everywhere.
        assert _row_count(str(db), "request_summaries", "rid-old") == 1
        assert _row_count(str(db), "decision_records", "rid-old") == 1
        assert _row_count(str(db), "debug_entries", "rid-old") == 1

        sink._run_cleanup_once()

        # rid-old fully evicted from all four tables.
        assert _row_count(str(db), "lifecycle_events", "rid-old") == 0
        assert _row_count(str(db), "request_summaries", "rid-old") == 0
        assert _row_count(str(db), "decision_records", "rid-old") == 0
        assert _row_count(str(db), "debug_entries", "rid-old") == 0

        # rid-new survives in all four tables.
        assert _row_count(str(db), "lifecycle_events", "rid-new") == 1
        assert _row_count(str(db), "request_summaries", "rid-new") == 1
        assert _row_count(str(db), "decision_records", "rid-new") == 1
        assert _row_count(str(db), "debug_entries", "rid-new") == 1
    finally:
        await sink.close()
