"""Non-blocking writer for the ``decision_records`` SQLite table.

Implements the ``LifecycleSink`` Protocol so the recorder slots into the
existing composite sink chain. On every ``DecisionEmitted`` event, the
recorder enqueues a row for asynchronous insertion into the dashboard
SQLite tier. Other event types are ignored.

The writer is non-blocking with respect to the calling pipeline: a full
queue or SQLite write failure increments a dropped-write counter and the
``DecisionEmitted`` event is silently lost from the dashboard tier
(observable lifecycle events still flow to the other sinks).

Concurrency: bounded ``asyncio.Queue`` + single background drain task
started lazily on the first ``emit`` call. ``close()`` flushes the queue
sentinel and awaits the drain task.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from arc_guard_core.decision import DecisionRecord
from arc_guard_core.lifecycle import LifecycleEvent

_LOG = logging.getLogger("arc_guard.dashboard.decision_recorder")


class DecisionRecordRecorder:
    """LifecycleSink that records ``DecisionEmitted`` events into SQLite."""

    def __init__(
        self,
        path: str | Path,
        *,
        queue_capacity: int = 1000,
        decision_lookup: Callable[[str], DecisionRecord | dict[str, Any] | None] | None = None,
    ) -> None:
        """``decision_lookup`` is an optional callable that resolves a
        ``decision_id`` to the full ``DecisionRecord`` payload. When None,
        the recorder writes only the metadata it can derive from the event
        (action, max_risk, decision_id) — the operator's pipeline must
        provide a richer ``decision_lookup`` to capture the full record."""
        self._path = str(path)
        self._queue: asyncio.Queue[tuple[str, str, str, str, int] | None] = asyncio.Queue(
            maxsize=queue_capacity
        )
        self._dropped_writes = 0
        self._closed = False
        self._drain_task: asyncio.Task[None] | None = None
        self._decision_lookup = decision_lookup
        self._conn: sqlite3.Connection | None = None

    @property
    def dropped_writes(self) -> int:
        return self._dropped_writes

    def _open_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                self._path,
                check_same_thread=False,
                isolation_level=None,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    async def emit(self, event: LifecycleEvent) -> None:
        if self._closed:
            return
        if type(event).event_type != "DecisionEmitted":
            return
        rid = event.rid
        decision_id = getattr(event, "decision_id", "")
        if not decision_id:
            return  # nothing to key by
        # Build payload: prefer the operator-supplied lookup; fall back to
        # the minimal event-derived dict.
        if self._decision_lookup is not None:
            try:
                rec = self._decision_lookup(decision_id)
            except Exception as exc:  # pragma: no cover — operator code
                _LOG.warning("decision_lookup raised for %s: %s", decision_id, exc)
                rec = None
        else:
            rec = None
        if isinstance(rec, DecisionRecord):
            payload = rec.__dict__
        elif isinstance(rec, dict):
            payload = rec
        else:
            payload = {
                "decision_id": decision_id,
                "action": getattr(event, "action", "pass"),
                "max_risk": getattr(event, "max_risk", "LOW"),
            }
        payload_json = json.dumps(payload, default=str)
        recorded_at = datetime.now(UTC).isoformat()
        row = (
            rid,
            decision_id,
            recorded_at,
            payload_json,
            len(payload_json),
        )
        # Start the drain task lazily on the first emission.
        if self._drain_task is None or self._drain_task.done():
            self._drain_task = asyncio.create_task(self._drain())
        try:
            self._queue.put_nowait(row)
        except asyncio.QueueFull:
            self._dropped_writes += 1
            _LOG.warning(
                "decision_records writer queue full; dropped rid=%s did=%s",
                rid,
                decision_id,
            )

    async def _drain(self) -> None:
        try:
            while not self._closed:
                row = await self._queue.get()
                if row is None:
                    break
                try:
                    conn = self._open_conn()
                    conn.execute(
                        "INSERT OR REPLACE INTO decision_records"
                        " (rid, decision_id, recorded_at,"
                        "  payload_json, payload_size_bytes)"
                        " VALUES (?, ?, ?, ?, ?)",
                        row,
                    )
                except sqlite3.Error as exc:
                    self._dropped_writes += 1
                    _LOG.warning(
                        "decision_records insert failed (rid=%s did=%s): %s",
                        row[0],
                        row[1],
                        exc,
                    )
        except asyncio.CancelledError:
            pass

    async def query(self, rid: str) -> list[LifecycleEvent] | None:
        return None

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        with suppress(asyncio.QueueFull):
            self._queue.put_nowait(None)
        if self._drain_task is not None:
            with suppress(asyncio.CancelledError):
                await self._drain_task
            self._drain_task = None
        if self._conn is not None:
            with suppress(sqlite3.Error):
                self._conn.close()
            self._conn = None


__all__ = ["DecisionRecordRecorder"]
