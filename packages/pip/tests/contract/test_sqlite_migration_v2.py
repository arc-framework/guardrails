"""Contract: schema v2 migration is idempotent and forward-only.

After construction, the SQLite store reports ``schema_version='2'``,
contains the three new dashboard tables, and re-running the migration
(by constructing a second sink against the same path) is a no-op that
preserves all existing data.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (name,),
    )
    return cur.fetchone() is not None


def _index_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name = ?",
        (name,),
    )
    return cur.fetchone() is not None


@pytest.mark.asyncio
async def test_fresh_sink_reports_schema_v2(tmp_path: Path) -> None:
    db = tmp_path / "fresh.db"
    sink = SqliteLifecycleSink(db)
    try:
        assert sink.schema_version == "2"
    finally:
        await sink.close()


@pytest.mark.asyncio
async def test_fresh_sink_creates_three_dashboard_tables(tmp_path: Path) -> None:
    db = tmp_path / "fresh.db"
    sink = SqliteLifecycleSink(db)
    try:
        conn = sqlite3.connect(db)
        try:
            assert _table_exists(conn, "lifecycle_events")
            assert _table_exists(conn, "request_summaries")
            assert _table_exists(conn, "decision_records")
            assert _table_exists(conn, "debug_entries")
        finally:
            conn.close()
    finally:
        await sink.close()


@pytest.mark.asyncio
async def test_fresh_sink_creates_dashboard_indexes(tmp_path: Path) -> None:
    db = tmp_path / "fresh.db"
    sink = SqliteLifecycleSink(db)
    try:
        conn = sqlite3.connect(db)
        try:
            for idx in (
                "idx_request_summaries_started_at",
                "idx_request_summaries_status_started",
                "idx_request_summaries_final_action",
                "idx_decision_records_rid",
                "idx_decision_records_recorded_at",
                "idx_debug_entries_ts",
            ):
                assert _index_exists(conn, idx), f"missing index: {idx}"
        finally:
            conn.close()
    finally:
        await sink.close()


@pytest.mark.asyncio
async def test_migration_is_idempotent(tmp_path: Path) -> None:
    """Constructing twice against the same path doesn't error; schema_version
    stays at "2"; existing meta values aren't duplicated."""
    db = tmp_path / "twice.db"
    sink_a = SqliteLifecycleSink(db)
    await sink_a.close()
    sink_b = SqliteLifecycleSink(db)
    try:
        assert sink_b.schema_version == "2"
        # Inspect the meta table directly — only one schema_version row.
        conn = sqlite3.connect(db)
        try:
            cur = conn.execute("SELECT COUNT(*) FROM lifecycle_meta WHERE key='schema_version'")
            assert cur.fetchone()[0] == 1
        finally:
            conn.close()
    finally:
        await sink_b.close()


@pytest.mark.asyncio
async def test_v1_db_upgraded_to_v2_on_open(tmp_path: Path) -> None:
    """A pre-existing v1 database (only the lifecycle_events + lifecycle_meta
    tables) is migrated forward when opened by a v2-aware sink. The new
    dashboard tables appear; the schema_version row updates from "1" to "2".
    """
    db = tmp_path / "v1.db"
    # Manually create a v1-shaped database.
    conn = sqlite3.connect(db)
    try:
        conn.executescript(
            """
            CREATE TABLE lifecycle_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE lifecycle_events (
                id TEXT PRIMARY KEY,
                rid TEXT NOT NULL,
                seq INTEGER NOT NULL,
                parent_id TEXT,
                event_type TEXT NOT NULL,
                event_data TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            INSERT INTO lifecycle_meta(key, value) VALUES('schema_version', '1');
            """
        )
        conn.commit()
    finally:
        conn.close()
    # Now open with the v2-aware sink — migration runs.
    sink = SqliteLifecycleSink(db)
    try:
        assert sink.schema_version == "2"
        conn = sqlite3.connect(db)
        try:
            assert _table_exists(conn, "request_summaries")
            assert _table_exists(conn, "decision_records")
            assert _table_exists(conn, "debug_entries")
        finally:
            conn.close()
    finally:
        await sink.close()
