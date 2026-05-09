"""Integration test: ``RidLogHandler`` taps stdlib log records into ``debug_entries``.

Verifies:
- A log record emitted while ``rid_context_var`` is set is captured.
- A log record emitted with no active rid is silently skipped.
- Concurrent contexts don't cross-pollinate (context-var per task).
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from pathlib import Path

import pytest

from arc_guard.observability.debug_entry_writer import DebugEntryWriter
from arc_guard.observability.debug_log_handler import (
    RidLogHandler,
    rid_context_var,
)
from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink


def _all_entries(path: str) -> list[sqlite3.Row]:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        return list(conn.execute("SELECT * FROM debug_entries ORDER BY rid, seq").fetchall())
    finally:
        conn.close()


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    db = tmp_path / "arc_guardrail.db"
    SqliteLifecycleSink(str(db))
    return str(db)


@pytest.mark.asyncio
async def test_record_with_active_rid_captured(db_path: str) -> None:
    writer = DebugEntryWriter(db_path)
    handler = RidLogHandler(writer)
    logger = logging.getLogger("arc_guard.test_capture")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        token = rid_context_var.set("rid-active")
        try:
            logger.debug("captured-message", extra={"custom": "yes"})
        finally:
            rid_context_var.reset(token)
        # Allow the writer's drain task to commit.
        await asyncio.sleep(0.1)
        rows = _all_entries(db_path)
        assert len(rows) == 1
        assert rows[0]["rid"] == "rid-active"
        assert rows[0]["message"] == "captured-message"
    finally:
        logger.removeHandler(handler)
        await writer.close()


@pytest.mark.asyncio
async def test_record_without_rid_skipped(db_path: str) -> None:
    writer = DebugEntryWriter(db_path)
    handler = RidLogHandler(writer)
    logger = logging.getLogger("arc_guard.test_skip")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        # No rid_context_var.set — emit should be skipped silently.
        logger.debug("orphan-message")
        await asyncio.sleep(0.05)
        rows = _all_entries(db_path)
        assert rows == []
    finally:
        logger.removeHandler(handler)
        await writer.close()


@pytest.mark.asyncio
async def test_concurrent_contexts_dont_bleed(db_path: str) -> None:
    """Each task has its own contextvar copy — concurrent rids don't mix."""
    writer = DebugEntryWriter(db_path)
    handler = RidLogHandler(writer)
    logger = logging.getLogger("arc_guard.test_concurrency")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:

        async def request(rid: str) -> None:
            token = rid_context_var.set(rid)
            try:
                logger.debug(f"hello from {rid}")
                await asyncio.sleep(0.01)
            finally:
                rid_context_var.reset(token)

        await asyncio.gather(
            request("rid-A"),
            request("rid-B"),
            request("rid-C"),
        )
        await asyncio.sleep(0.1)
        rows = _all_entries(db_path)
        rid_to_msg = {r["rid"]: r["message"] for r in rows}
        assert rid_to_msg == {
            "rid-A": "hello from rid-A",
            "rid-B": "hello from rid-B",
            "rid-C": "hello from rid-C",
        }
    finally:
        logger.removeHandler(handler)
        await writer.close()
