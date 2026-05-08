"""Persistent `LifecycleSink` backed by a SQLite database file.

Schema is one row per event with the typed payload serialized as a JSON
string in the `event_data` column (uses SQLite JSON1 implicitly via column
storage; we don't run JSON queries against it, just store/load). Indexes on
`rid` and `created_at` keep lookup + retention scans cheap.

Concurrency: a single `sqlite3.Connection` opened with
`check_same_thread=False`. All writes happen on the asyncio event loop; the
Python `sqlite3` module's GIL-protected operations are atomic enough for
the single-instance deployment target. Operators wanting multi-process
write fan-out should wire an external sink instead.

Failure mode: open. Database errors are logged + counted; never propagate
back into the calling pipeline.

Retention: every `cleanup_interval_seconds` a background task deletes rows
older than `max_age_days` OR beyond `max_rows` (whichever is stricter).
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from contextlib import suppress
from dataclasses import asdict, fields
from datetime import datetime
from pathlib import Path
from typing import Any

from arc_guard_core.lifecycle import (
    ALL_EVENT_TYPES,
    LifecycleEvent,
    LifecycleEventBase,
)

_LOG = logging.getLogger("arc_guard.lifecycle.sqlite")

_SCHEMA_VERSION = "2"

# v1 schema — the original lifecycle store.
_SCHEMA_SQL_V1 = """
CREATE TABLE IF NOT EXISTS lifecycle_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lifecycle_events (
    id TEXT PRIMARY KEY,
    rid TEXT NOT NULL,
    seq INTEGER NOT NULL,
    parent_id TEXT,
    event_type TEXT NOT NULL,
    event_data TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_lifecycle_events_rid ON lifecycle_events(rid);
CREATE INDEX IF NOT EXISTS idx_lifecycle_events_created_at ON lifecycle_events(created_at);
"""

# v2 schema — three new tables for the dashboard data plane.
# Forward-only migration: every statement uses IF NOT EXISTS so re-running
# is idempotent. Retention coupling lives in `_run_cleanup_once`, which
# evicts rows from these tables in lockstep with `lifecycle_events`.
_SCHEMA_SQL_V2 = """
CREATE TABLE IF NOT EXISTS request_summaries (
    rid TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    last_event_at TEXT NOT NULL,
    status TEXT NOT NULL,
    final_action TEXT,
    max_risk REAL,
    duration_ms INTEGER,
    refusal_code TEXT,
    decision_id TEXT,
    live INTEGER NOT NULL DEFAULT 1,
    stage TEXT
);

CREATE INDEX IF NOT EXISTS idx_request_summaries_started_at
    ON request_summaries(started_at);
CREATE INDEX IF NOT EXISTS idx_request_summaries_status_started
    ON request_summaries(status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_request_summaries_final_action
    ON request_summaries(final_action);

CREATE TABLE IF NOT EXISTS decision_records (
    rid TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_size_bytes INTEGER NOT NULL,
    PRIMARY KEY (rid, decision_id)
);

CREATE INDEX IF NOT EXISTS idx_decision_records_rid
    ON decision_records(rid);
CREATE INDEX IF NOT EXISTS idx_decision_records_recorded_at
    ON decision_records(recorded_at);

CREATE TABLE IF NOT EXISTS debug_entries (
    rid TEXT NOT NULL,
    seq INTEGER NOT NULL,
    ts TEXT NOT NULL,
    channel TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (rid, seq)
);

CREATE INDEX IF NOT EXISTS idx_debug_entries_ts
    ON debug_entries(ts);
"""


# Build a class-name → dataclass map once at import time so deserialization
# doesn't pay for `getattr` lookups per row.
_EVENT_TYPES_BY_NAME: dict[str, type[LifecycleEventBase]] = {
    cls.event_type: cls  # type: ignore[attr-defined]
    for cls in ALL_EVENT_TYPES
}


def _event_to_row(event: LifecycleEvent) -> tuple[str, str, int, str | None, str, str, float]:
    """Serialize one event to the seven-column row tuple."""
    cls = type(event)
    payload = asdict(event)
    payload["event_type"] = cls.event_type
    for k, v in list(payload.items()):
        if isinstance(v, datetime):
            payload[k] = v.isoformat()
        elif isinstance(v, tuple):
            payload[k] = list(v)
    created_at = event.ts.timestamp()
    return (
        event.id,
        event.rid,
        event.seq,
        event.parent_id,
        cls.event_type,
        json.dumps(payload),
        created_at,
    )


def _row_to_event(row: sqlite3.Row | tuple[Any, ...]) -> LifecycleEvent | None:
    """Deserialize a row into a typed `LifecycleEvent`, or None if event_type
    is unknown (forward-compatibility: a v2 reader against a v1 row should
    skip rather than crash if a new event type was added later)."""
    event_type = row["event_type"] if isinstance(row, sqlite3.Row) else row[4]
    cls = _EVENT_TYPES_BY_NAME.get(event_type)
    if cls is None:
        _LOG.warning("unknown event_type %r in sqlite row; skipping", event_type)
        return None
    raw = row["event_data"] if isinstance(row, sqlite3.Row) else row[5]
    payload = json.loads(raw)
    payload.pop("event_type", None)  # not a constructor arg; ClassVar
    # Coerce the universal `ts` field back from ISO 8601 to datetime.
    if "ts" in payload and isinstance(payload["ts"], str):
        payload["ts"] = datetime.fromisoformat(payload["ts"])
    # Coerce list-shaped tuple fields back to tuples.
    for f in fields(cls):
        if f.name in payload and isinstance(payload[f.name], list):
            origin = getattr(f.type, "__origin__", None)
            if origin is tuple or (
                isinstance(f.type, str) and f.type.startswith("tuple[")
            ):
                payload[f.name] = tuple(payload[f.name])
    return cls(**payload)  # type: ignore[return-value]


class SqliteLifecycleSink:
    """LifecycleSink: persistent storage in a SQLite file with retention."""

    last_served_from = "sqlite"  # consumed by lifecycle.py replay endpoint

    def __init__(
        self,
        path: str | Path,
        *,
        max_rows: int = 500_000,
        max_age_days: int = 7,
        cleanup_interval_seconds: float = 60.0,
    ) -> None:
        if max_rows < 1:
            raise ValueError("max_rows must be >= 1")
        if max_age_days < 1:
            raise ValueError("max_age_days must be >= 1")
        if cleanup_interval_seconds <= 0:
            raise ValueError("cleanup_interval_seconds must be > 0")
        self._path = str(path)
        self._max_rows = max_rows
        self._max_age_seconds = max_age_days * 86400
        self._cleanup_interval_seconds = cleanup_interval_seconds
        self._closed = False
        self._cleanup_task: asyncio.Task[None] | None = None

        # Ensure the parent directory exists. Operators typically configure
        # an absolute path (e.g. /data/arc_guardrail.db); auto-creating the
        # directory means a fresh deployment doesn't require an mkdir step.
        # The `:memory:` sentinel is left unchanged.
        if self._path != ":memory:":
            parent = Path(self._path).parent
            if str(parent) and not parent.exists():
                parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(
            self._path,
            check_same_thread=False,
            isolation_level=None,  # autocommit; we manage transactions explicitly
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._migrate_schema()

    def _migrate_schema(self) -> None:
        """Forward-only schema migration. Every statement uses IF NOT EXISTS
        so re-running is a no-op. After v1 + v2 DDL, the meta row is upserted
        to the current `_SCHEMA_VERSION` so subsequent reads see the correct
        version regardless of which migrations were run."""
        self._conn.executescript(_SCHEMA_SQL_V1)
        self._conn.executescript(_SCHEMA_SQL_V2)
        # UPSERT — the original code used INSERT OR IGNORE, which left existing
        # rows at "1" forever. Use ON CONFLICT to bring the value forward.
        self._conn.execute(
            "INSERT INTO lifecycle_meta(key, value) VALUES('schema_version', ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (_SCHEMA_VERSION,),
        )

    @property
    def path(self) -> str:
        return self._path

    @property
    def schema_version(self) -> str:
        cur = self._conn.execute(
            "SELECT value FROM lifecycle_meta WHERE key='schema_version'"
        )
        row = cur.fetchone()
        return str(row[0]) if row is not None else "0"

    def __len__(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM lifecycle_events")
        return int(cur.fetchone()[0])

    async def emit(self, event: LifecycleEvent) -> None:
        if self._closed:
            return
        try:
            row = _event_to_row(event)
            self._conn.execute(
                "INSERT OR IGNORE INTO lifecycle_events"
                " (id, rid, seq, parent_id, event_type, event_data, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                row,
            )
        except sqlite3.Error as exc:  # pragma: no cover — rare
            _LOG.warning("sqlite emit failed for event id=%s: %s", event.id, exc)

    async def query(self, rid: str) -> list[LifecycleEvent] | None:
        if self._closed:
            return None
        try:
            cur = self._conn.execute(
                "SELECT * FROM lifecycle_events WHERE rid = ? ORDER BY seq ASC",
                (rid,),
            )
            rows = cur.fetchall()
        except sqlite3.Error as exc:
            _LOG.warning("sqlite query failed for rid=%s: %s", rid, exc)
            return None
        if not rows:
            return None
        events = [_row_to_event(r) for r in rows]
        return [e for e in events if e is not None]

    def start_cleanup_task(self) -> None:
        """Start the periodic retention background task. Called by the api
        transport after the asyncio event loop is established (typically in
        the FastAPI lifespan startup phase). Safe to call once; subsequent
        calls are no-ops."""
        if self._cleanup_task is not None and not self._cleanup_task.done():
            return
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        try:
            while not self._closed:
                await asyncio.sleep(self._cleanup_interval_seconds)
                if self._closed:
                    break
                self._run_cleanup_once()
        except asyncio.CancelledError:
            pass

    def _run_cleanup_once(self) -> int:
        """Delete rows older than `max_age_days` OR beyond `max_rows` from
        `lifecycle_events`, then evict the same set of `rid`s from the three
        dashboard tables (`debug_entries`, `decision_records`,
        `request_summaries`) in the same transaction. Returns the number of
        `lifecycle_events` rows deleted."""
        try:
            now = time.time()
            cutoff = now - self._max_age_seconds
            self._conn.execute("BEGIN")
            try:
                # Identify the set of rids we're about to evict. Materialize
                # into a temp table so the four delete statements all see the
                # same eviction set even if `lifecycle_events` is changing.
                self._conn.execute(
                    "CREATE TEMP TABLE IF NOT EXISTS _evict_rids (rid TEXT PRIMARY KEY)"
                )
                self._conn.execute("DELETE FROM _evict_rids")
                self._conn.execute(
                    "INSERT OR IGNORE INTO _evict_rids(rid)"
                    " SELECT DISTINCT rid FROM lifecycle_events"
                    " WHERE created_at < ?"
                    "    OR rowid <= (SELECT MAX(rowid) - ? FROM lifecycle_events)",
                    (cutoff, self._max_rows),
                )
                # Delete the dashboard rows first (no FK enforced, but order
                # matches the documented intent: child resources before parent).
                self._conn.execute(
                    "DELETE FROM debug_entries WHERE rid IN (SELECT rid FROM _evict_rids)"
                )
                self._conn.execute(
                    "DELETE FROM decision_records WHERE rid IN (SELECT rid FROM _evict_rids)"
                )
                self._conn.execute(
                    "DELETE FROM request_summaries WHERE rid IN (SELECT rid FROM _evict_rids)"
                )
                cur = self._conn.execute(
                    "DELETE FROM lifecycle_events"
                    " WHERE rid IN (SELECT rid FROM _evict_rids)"
                )
                deleted = cur.rowcount
                self._conn.execute("COMMIT")
            except sqlite3.Error:
                with suppress(sqlite3.Error):
                    self._conn.execute("ROLLBACK")
                raise
            if deleted > 0:
                _LOG.info(
                    "retention cleanup evicted %d lifecycle_events rows"
                    " and the matching dashboard rows",
                    deleted,
                )
            return int(deleted)
        except sqlite3.Error as exc:
            _LOG.warning("retention cleanup failed: %s", exc)
            return 0

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._cleanup_task
            self._cleanup_task = None
        with suppress(sqlite3.Error):
            self._conn.close()


__all__ = ["SqliteLifecycleSink"]
