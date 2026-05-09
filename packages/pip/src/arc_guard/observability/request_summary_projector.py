"""Writer-side projection from ``LifecycleEvent`` stream to ``request_summaries`` rows.

Implements the ``LifecycleSink`` Protocol so the projector slots into the
existing composite sink chain alongside ``RingBufferLifecycleSink`` and
``SqliteLifecycleSink``. On each event, the projector upserts a single
row keyed by ``rid`` in the dashboard-data-plane SQLite store.

Failure mode: open. Database errors are logged + counted via the dropped
counter; they never propagate back into the calling pipeline. The
non-blocking-reporter discipline mirrors ``SqliteLifecycleSink``.

Concurrency: each projector owns its own ``sqlite3.Connection`` opened
with ``check_same_thread=False`` and ``isolation_level=None``. Multiple
sinks against the same database file are safe under WAL.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import suppress
from datetime import datetime
from pathlib import Path

from arc_guard_core.lifecycle import LifecycleEvent

_LOG = logging.getLogger("arc_guard.dashboard.summary_projector")


def _iso(ts: datetime) -> str:
    return ts.isoformat()


class RequestSummaryProjector:
    """LifecycleSink that maintains the ``request_summaries`` table."""

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        self._closed = False
        self._dropped_writes = 0
        self._conn = sqlite3.connect(
            self._path,
            check_same_thread=False,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")

    @property
    def dropped_writes(self) -> int:
        return self._dropped_writes

    async def emit(self, event: LifecycleEvent) -> None:
        if self._closed:
            return
        try:
            self._project(event)
        except sqlite3.Error as exc:
            self._dropped_writes += 1
            _LOG.warning(
                "request_summaries projector dropped event id=%s rid=%s: %s",
                event.id,
                event.rid,
                exc,
            )

    def _project(self, event: LifecycleEvent) -> None:
        et = type(event).event_type
        rid = event.rid
        ts_iso = _iso(event.ts)

        if et == "RequestStarted":
            # Insert-or-noop: a duplicate RequestStarted for the same rid
            # is a bug elsewhere; we silently keep the first row's timing.
            self._conn.execute(
                "INSERT OR IGNORE INTO request_summaries"
                " (rid, started_at, last_event_at, status, live)"
                " VALUES (?, ?, ?, 'live', 1)",
                (rid, ts_iso, ts_iso),
            )
            return

        # Every other event bumps last_event_at.
        self._conn.execute(
            "UPDATE request_summaries SET last_event_at = ? WHERE rid = ?",
            (ts_iso, rid),
        )

        if et == "StageRan":
            self._conn.execute(
                "UPDATE request_summaries SET stage = ? WHERE rid = ?",
                (getattr(event, "stage", None), rid),
            )
        elif et == "FindingProduced":
            score = float(getattr(event, "score", 0.0))
            self._conn.execute(
                "UPDATE request_summaries"
                " SET max_risk = MAX(COALESCE(max_risk, 0.0), ?) WHERE rid = ?",
                (score, rid),
            )
        elif et == "DecisionEmitted":
            self._conn.execute(
                "UPDATE request_summaries"
                " SET decision_id = ?, final_action = ? WHERE rid = ?",
                (
                    getattr(event, "decision_id", None),
                    getattr(event, "action", None),
                    rid,
                ),
            )
        elif et == "RefusalProduced":
            self._conn.execute(
                "UPDATE request_summaries"
                " SET refusal_code = ? WHERE rid = ?",
                (getattr(event, "refusal_code", None), rid),
            )
        elif et == "RequestCompleted":
            blocked = bool(getattr(event, "blocked", False))
            pre_action = getattr(event, "pre_action", "pass")
            post_action = getattr(event, "post_action", None)
            final_action = (
                "block" if blocked
                else (post_action or pre_action or "pass")
            )
            duration_ms = int(getattr(event, "total_duration_ms", 0.0))
            self._conn.execute(
                "UPDATE request_summaries"
                " SET status = 'completed', live = 0,"
                "     duration_ms = ?,"
                "     final_action = COALESCE(final_action, ?)"
                " WHERE rid = ?",
                (duration_ms, final_action, rid),
            )

    async def query(self, rid: str) -> list[LifecycleEvent] | None:
        # Projector does not store events — only projections. Composite
        # query() fall-through skips this sink.
        return None

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        with suppress(sqlite3.Error):
            self._conn.close()


__all__ = ["RequestSummaryProjector"]
