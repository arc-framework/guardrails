"""Integration test: all three dashboard resources survive a service restart.

Populates ``request_summaries``, ``decision_records``, and ``debug_entries``
for a known ``rid``, simulates a restart by tearing down the app and
recreating it against the same SQLite file, and asserts all four read
endpoints (``/requests/{rid}``, ``/lifecycle/{rid}``,
``/requests/{rid}/decision``, ``/requests/{rid}/debug``) still return
200 with the same payloads.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink
from arc_guard_core.lifecycle.events import (
    RequestCompleted,
    RequestStarted,
)

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


def _seed_rid(path: str, rid: str) -> None:
    """Seed all three dashboard tables plus a lifecycle event for the rid."""
    conn = sqlite3.connect(path)
    ts = datetime(2026, 5, 9, 14, 0, 0, tzinfo=UTC).isoformat()
    try:
        conn.execute(
            "INSERT INTO request_summaries"
            " (rid, started_at, last_event_at, status, final_action,"
            "  max_risk, duration_ms, decision_id, live, stage)"
            " VALUES (?, ?, ?, 'completed', 'pass', 0.1, 50, 'dec-x', 0, 'report')",
            (rid, ts, ts),
        )
        body = json.dumps({"decision_id": "dec-x", "action": "pass"})
        conn.execute(
            "INSERT INTO decision_records"
            " (rid, decision_id, recorded_at, payload_json, payload_size_bytes)"
            " VALUES (?, 'dec-x', ?, ?, ?)",
            (rid, ts, body, len(body)),
        )
        conn.execute(
            "INSERT INTO debug_entries"
            " (rid, seq, ts, channel, severity, message, metadata_json)"
            " VALUES (?, 1, ?, 'arc_guard.test', 'DEBUG', 'first', '{}')",
            (rid, ts),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_all_three_resources_survive_restart(tmp_path: Path) -> None:
    db = tmp_path / "arc_guardrail.db"

    # First service lifecycle: open sink, seed durable rows, also seed a
    # lifecycle_events row so /lifecycle/{rid} resolves.
    sink_a = SqliteLifecycleSink(str(db))
    ts = datetime(2026, 5, 9, 14, 0, 0, tzinfo=UTC)
    try:
        await sink_a.emit(
            RequestStarted(id="ev-1", parent_id=None, seq=1, ts=ts, rid="rid-restart")
        )
        await sink_a.emit(
            RequestCompleted(
                id="ev-2",
                parent_id="ev-1",
                seq=2,
                ts=ts,
                rid="rid-restart",
                blocked=False,
                pre_action="pass",
                total_duration_ms=50.0,
            )
        )
    finally:
        await sink_a.close()
    _seed_rid(str(db), "rid-restart")

    # Second service lifecycle: open a fresh app against the same DB file.
    settings = ServiceSettings(enable_chat_completions=False, lifecycle_sqlite_path=str(db))
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        # All four endpoints resolve.
        summary_resp = await c.get("/requests/rid-restart")
        assert summary_resp.status_code == 200
        assert summary_resp.json()["summary"]["rid"] == "rid-restart"

        lifecycle_resp = await c.get("/lifecycle/rid-restart")
        assert lifecycle_resp.status_code == 200
        assert len(lifecycle_resp.json()["events"]) >= 2

        decision_resp = await c.get("/requests/rid-restart/decision")
        assert decision_resp.status_code == 200
        assert decision_resp.json()["decision_id"] == "dec-x"

        debug_resp = await c.get("/requests/rid-restart/debug")
        assert debug_resp.status_code == 200
        assert len(debug_resp.json()["items"]) == 1
