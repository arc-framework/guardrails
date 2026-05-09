"""Stale-live sweeper: promotes hung ``request_summaries.live=1`` rows to
``status='errored'`` by emitting a ``RequestErrored`` event for each.

Resolves F6: orphaned live rows pile up when a backend hangs past the
operator-acceptable window. The sweeper runs as a background asyncio
task started from the api transport's ``_start_sink_background_tasks``
hook (the same path that starts the SqliteLifecycleSink retention task).

The sweeper does NOT mutate ``request_summaries`` directly — it emits
``RequestErrored`` events through the configured ``LifecycleSink``.
Downstream sinks (the projector, SQLite tier, SSE broadcaster) handle
the row update + persistence + fan-out consistently.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from arc_guard_core.lifecycle import RequestErrored, new_event_id

_LOG = logging.getLogger("arc_guard.observability.stale_live_sweeper")


class StaleLiveSweeper:
    """Periodic task that detects and resolves stale live=1 rows.

    Reads ``request_summaries`` directly via SQLite (read-only path); writes
    happen via the configured ``LifecycleSink``'s ``emit`` so the
    projector, SQLite tier, and SSE broadcaster all see the transition
    consistently.

    Lifecycle:
    - Construct with the SQLite path + lifecycle sink + thresholds.
    - Call ``start_cleanup_task()`` once after the asyncio loop is up.
    - Call ``await close()`` at shutdown.

    Thresholds:
    - ``stale_threshold_seconds`` — how stale a row's ``last_event_at``
      must be before promotion. Default 600 (~10 minutes).
    - ``sweep_interval_seconds`` — how often the sweeper polls. Default
      60. Set to ``<= 0`` to disable the sweeper entirely (off-switch).
    """

    def __init__(
        self,
        *,
        path: str,
        lifecycle_sink: Any,
        stale_threshold_seconds: int = 600,
        sweep_interval_seconds: int = 60,
    ) -> None:
        self._path = path
        self._sink = lifecycle_sink
        self._stale_threshold_seconds = int(stale_threshold_seconds)
        self._sweep_interval_seconds = int(sweep_interval_seconds)
        self._task: asyncio.Task[None] | None = None
        self._closed = False
        self._read_conn: sqlite3.Connection | None = None
        if self._sweep_interval_seconds > 0:
            self._read_conn = sqlite3.connect(
                self._path, isolation_level=None, check_same_thread=False
            )

    def start_cleanup_task(self) -> None:
        """Start the periodic sweep background task. No-op when the sweep
        interval is non-positive (off-switch). Safe to call once; subsequent
        calls are no-ops."""
        if self._sweep_interval_seconds <= 0:
            return
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._sweep_loop())

    async def _sweep_loop(self) -> None:
        try:
            while not self._closed:
                await asyncio.sleep(self._sweep_interval_seconds)
                if self._closed:
                    break
                await self._run_sweep_once()
        except asyncio.CancelledError:
            pass

    async def _run_sweep_once(self) -> int:
        """Find stale live=1 rows and emit RequestErrored for each. Returns
        the number of rows promoted. Wrapped in try/except so a transient
        SQLite error never tears the loop down."""
        if self._read_conn is None:
            return 0
        sweep_started = time.perf_counter()
        try:
            stale_rids = self._query_stale_rids()
        except sqlite3.Error as exc:
            _LOG.warning("stale_live_sweep query failed: %s", exc)
            return 0
        promoted = 0
        for rid, last_event_at_iso in stale_rids:
            try:
                last_seq = self._query_last_seq(rid)
                event = RequestErrored(
                    id=new_event_id(),
                    parent_id=None,
                    seq=last_seq + 1,
                    ts=datetime.now(UTC),
                    rid=rid,
                    reason="stale_live_sweep",
                    terminated_by="stale_live_sweeper",
                    last_event_seq=last_seq,
                )
                await self._sink.emit(event)
                promoted += 1
                _LOG.warning(
                    "event=stale_live_sweep_promoted rid=%s last_event_at=%s "
                    "seconds_since_last_event=%d",
                    rid,
                    last_event_at_iso,
                    self._seconds_since(last_event_at_iso),
                )
            except Exception as exc:  # noqa: BLE001
                _LOG.warning(
                    "stale_live_sweep failed to promote rid=%s: %s",
                    rid,
                    exc,
                )
        duration_ms = (time.perf_counter() - sweep_started) * 1000
        _LOG.info(
            "event=stale_live_sweep_completed swept_count=%d duration_ms=%.1f threshold_seconds=%d",
            promoted,
            duration_ms,
            self._stale_threshold_seconds,
        )
        return promoted

    def _query_stale_rids(self) -> list[tuple[str, str]]:
        assert self._read_conn is not None
        cutoff_iso = (
            datetime.fromtimestamp(time.time() - self._stale_threshold_seconds, tz=UTC)
            .isoformat()
            .replace("+00:00", "Z")
        )
        cur = self._read_conn.execute(
            "SELECT rid, last_event_at FROM request_summaries WHERE live = 1 AND last_event_at < ?",
            (cutoff_iso,),
        )
        return [(r[0], r[1]) for r in cur.fetchall()]

    def _query_last_seq(self, rid: str) -> int:
        assert self._read_conn is not None
        cur = self._read_conn.execute(
            "SELECT COALESCE(MAX(seq), 0) FROM lifecycle_events WHERE rid = ?",
            (rid,),
        )
        row = cur.fetchone()
        return int(row[0]) if row else 0

    @staticmethod
    def _seconds_since(iso_ts: str) -> int:
        try:
            ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
            return int((datetime.now(UTC) - ts).total_seconds())
        except ValueError:
            return -1

    async def emit(self, event: Any) -> None:
        """The sweeper itself is not a sink — it has nothing to record on
        forward emissions. The composite walks past it gracefully because
        it doesn't appear in the children list."""
        return None

    async def query(self, rid: str) -> list[Any] | None:
        return None

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
        if self._read_conn is not None:
            with suppress(sqlite3.Error):
                self._read_conn.close()


__all__ = ["StaleLiveSweeper"]
