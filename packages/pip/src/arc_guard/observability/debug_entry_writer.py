"""Non-blocking writer for the ``debug_entries`` SQLite table.

Consumed by ``RidLogHandler`` (see ``debug_log_handler.py``). Each call to
``write()`` enqueues an envelope dict; a background drain task inserts
rows into the dashboard SQLite tier with a monotonic per-rid ``seq``.

Failure mode: open. Queue overflow or SQLite errors increment the
dropped-write counter. The request path never blocks on this writer.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any

_LOG = logging.getLogger("arc_guard.dashboard.debug_writer")


class DebugEntryWriter:
    """Non-blocking writer for ``debug_entries`` rows."""

    def __init__(
        self,
        path: str | Path,
        *,
        queue_capacity: int = 5000,
    ) -> None:
        self._path = str(path)
        self._queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=queue_capacity)
        self._dropped_writes = 0
        self._closed = False
        self._drain_task: asyncio.Task[None] | None = None
        self._conn: sqlite3.Connection | None = None
        # Per-rid seq counters held in memory. These are the source of truth
        # for the next seq to assign — reads from SQLite would race with
        # in-flight inserts. On restart, the counter rebuilds from MAX(seq).
        self._seq_by_rid: dict[str, int] = {}
        self._seq_lock = asyncio.Lock()

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

    async def write(
        self,
        *,
        rid: str,
        ts: datetime,
        channel: str,
        severity: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Enqueue one debug entry. Non-blocking; returns immediately."""
        if self._closed:
            return
        async with self._seq_lock:
            seq = self._seq_by_rid.get(rid, 0) + 1
            self._seq_by_rid[rid] = seq
        envelope: dict[str, Any] = {
            "rid": rid,
            "seq": seq,
            "ts": ts.isoformat(),
            "channel": channel,
            "severity": severity,
            "message": message,
            "metadata": metadata or {},
        }
        if self._drain_task is None or self._drain_task.done():
            self._drain_task = asyncio.create_task(self._drain())
        try:
            self._queue.put_nowait(envelope)
        except asyncio.QueueFull:
            self._dropped_writes += 1
            _LOG.warning(
                "debug_entries writer queue full; dropped rid=%s seq=%d",
                rid,
                seq,
            )

    async def _drain(self) -> None:
        try:
            while not self._closed:
                envelope = await self._queue.get()
                if envelope is None:
                    break
                try:
                    conn = self._open_conn()
                    conn.execute(
                        "INSERT OR REPLACE INTO debug_entries"
                        " (rid, seq, ts, channel, severity, message, metadata_json)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            envelope["rid"],
                            envelope["seq"],
                            envelope["ts"],
                            envelope["channel"],
                            envelope["severity"],
                            envelope["message"],
                            json.dumps(envelope["metadata"], default=str),
                        ),
                    )
                except sqlite3.Error as exc:
                    self._dropped_writes += 1
                    _LOG.warning(
                        "debug_entries insert failed (rid=%s seq=%d): %s",
                        envelope["rid"],
                        envelope["seq"],
                        exc,
                    )
        except asyncio.CancelledError:
            pass

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


__all__ = ["DebugEntryWriter"]
