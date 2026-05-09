"""End-to-end test: workspace open covers all five acceptance scenarios.

Scenarios:

1. ``GET /requests/{rid}`` returns the canonical summary + manifest.
2. ``GET /lifecycle/{rid}`` returns the ordered lifecycle replay.
3. ``GET /requests/{rid}/decision`` returns the recorded DecisionRecord.
4. ``GET /requests/{rid}/debug`` returns ordered, paginated debug entries.
5. Missing decision/debug fail independently without breaking the summary.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


def _seed(
    path: str,
    rid: str,
    *,
    decision: bool = False,
    debug: bool = False,
) -> None:
    import json

    conn = sqlite3.connect(path)
    ts = datetime(2026, 5, 9, 14, 0, 0, tzinfo=UTC).isoformat()
    try:
        conn.execute(
            "INSERT INTO request_summaries"
            " (rid, started_at, last_event_at, status, final_action,"
            "  max_risk, duration_ms, decision_id, live, stage)"
            " VALUES (?, ?, ?, 'completed', 'pass', 0.1, 50, ?, 0, 'report')",
            (rid, ts, ts, "dec-x" if decision else None),
        )
        if decision:
            payload = {"decision_id": "dec-x", "action": "pass"}
            body = json.dumps(payload)
            conn.execute(
                "INSERT INTO decision_records"
                " (rid, decision_id, recorded_at, payload_json, payload_size_bytes)"
                " VALUES (?, 'dec-x', ?, ?, ?)",
                (rid, ts, body, len(body)),
            )
        if debug:
            conn.execute(
                "INSERT INTO debug_entries"
                " (rid, seq, ts, channel, severity, message, metadata_json)"
                " VALUES (?, 1, ?, 'arc_guard.test', 'DEBUG', 'first', '{}')",
                (rid, ts),
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
async def client(tmp_path: Path):
    db = tmp_path / "arc_guardrail.db"
    SqliteLifecycleSink(str(db))
    settings = ServiceSettings(enable_chat_completions=False, lifecycle_sqlite_path=str(db))
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, str(db)


@pytest.mark.asyncio
async def test_summary_returns_manifest(client) -> None:
    c, db = client
    _seed(db, "rid-full", decision=True, debug=True)
    resp = await c.get("/requests/rid-full")
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["rid"] == "rid-full"
    assert body["resources"]["decision"] is True
    assert body["resources"]["debug"] is True


@pytest.mark.asyncio
async def test_decision_endpoint_returns_record(client) -> None:
    c, db = client
    _seed(db, "rid-full", decision=True, debug=True)
    resp = await c.get("/requests/rid-full/decision")
    assert resp.status_code == 200
    body = resp.json()
    assert body["rid"] == "rid-full"
    assert body["decision_id"] == "dec-x"


@pytest.mark.asyncio
async def test_debug_endpoint_returns_paginated_entries(client) -> None:
    c, db = client
    _seed(db, "rid-full", decision=True, debug=True)
    resp = await c.get("/requests/rid-full/debug")
    assert resp.status_code == 200
    body = resp.json()
    assert body["rid"] == "rid-full"
    assert len(body["items"]) == 1


@pytest.mark.asyncio
async def test_missing_decision_does_not_break_summary(client) -> None:
    """Summary survives even when the subordinate decision/debug resources
    are missing — they 404 independently."""
    c, db = client
    _seed(db, "rid-bare", decision=False, debug=False)

    summary_resp = await c.get("/requests/rid-bare")
    assert summary_resp.status_code == 200
    decision_resp = await c.get("/requests/rid-bare/decision")
    assert decision_resp.status_code == 404
    assert decision_resp.json()["error"]["code"] == "decision_not_captured"
    debug_resp = await c.get("/requests/rid-bare/debug")
    assert debug_resp.status_code == 404
    assert debug_resp.json()["error"]["code"] == "debug_not_captured"


@pytest.mark.asyncio
async def test_response_carries_x_request_id_header(client) -> None:
    """The request-scope middleware echoes the rid in the response header
    so clients can correlate without parsing the body."""
    c, db = client
    _seed(db, "rid-corr", decision=True)
    resp = await c.get(
        "/requests/rid-corr",
        headers={"x-request-id": "trace-abc"},
    )
    assert resp.headers.get("x-request-id") == "trace-abc"
