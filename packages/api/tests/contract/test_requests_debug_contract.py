"""Contract: ``GET /requests/{rid}/debug`` cursor pagination contract."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink
from arc_guard_core.schemas import RequestDebugPage, encode_debug_cursor

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


def _seed_debug_entry(path: str, rid: str, seq: int, *, severity: str = "DEBUG") -> None:
    import json

    conn = sqlite3.connect(path)
    ts = datetime(2026, 5, 9, 14, 0, seq, tzinfo=UTC).isoformat()
    try:
        conn.execute(
            "INSERT INTO debug_entries"
            " (rid, seq, ts, channel, severity, message, metadata_json)"
            " VALUES (?, ?, ?, 'arc_guard.test', ?, ?, ?)",
            (rid, seq, ts, severity, f"line {seq}", json.dumps({"i": seq})),
        )
        # Also seed a request_summary so the rid is "known"
        conn.execute(
            "INSERT OR IGNORE INTO request_summaries"
            " (rid, started_at, last_event_at, status, live)"
            " VALUES (?, ?, ?, 'completed', 0)",
            (rid, ts, ts),
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
async def test_returns_page_with_cursor_when_more_remain(client) -> None:
    c, db = client
    for i in range(1, 6):
        _seed_debug_entry(db, "rid-1", i)
    resp = await c.get("/requests/rid-1/debug?page_size=3")
    assert resp.status_code == 200
    page = RequestDebugPage.model_validate(resp.json())
    assert len(page.items) == 3
    assert page.next_cursor is not None


@pytest.mark.asyncio
async def test_cursor_walks_to_tail(client) -> None:
    c, db = client
    for i in range(1, 6):
        _seed_debug_entry(db, "rid-1", i)
    resp1 = await c.get("/requests/rid-1/debug?page_size=3")
    page1 = RequestDebugPage.model_validate(resp1.json())
    resp2 = await c.get(f"/requests/rid-1/debug?page_size=3&cursor={page1.next_cursor}")
    page2 = RequestDebugPage.model_validate(resp2.json())
    assert len(page2.items) == 2  # remaining
    assert page2.next_cursor is None


@pytest.mark.asyncio
async def test_cursor_mismatch_returns_400(client) -> None:
    c, db = client
    _seed_debug_entry(db, "rid-1", 1)
    bogus = encode_debug_cursor(rid="other-rid", seq=0)
    resp = await c.get(f"/requests/rid-1/debug?cursor={bogus}")
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["code"] == "cursor_mismatch"


@pytest.mark.asyncio
async def test_invalid_cursor_returns_400(client) -> None:
    c, db = client
    _seed_debug_entry(db, "rid-1", 1)
    resp = await c.get("/requests/rid-1/debug?cursor=not-base64!")
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["code"] == "cursor_invalid"


@pytest.mark.asyncio
async def test_404_when_debug_not_captured(client) -> None:
    c, db = client
    # Seed a request_summary but no debug entries.
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "INSERT INTO request_summaries"
            " (rid, started_at, last_event_at, status, live)"
            " VALUES ('rid-empty', '2026-05-09T00:00:00+00:00',"
            "         '2026-05-09T00:00:00+00:00', 'completed', 0)"
        )
        conn.commit()
    finally:
        conn.close()
    resp = await c.get("/requests/rid-empty/debug")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "debug_not_captured"


@pytest.mark.asyncio
async def test_404_when_rid_unknown(client) -> None:
    c, _ = client
    resp = await c.get("/requests/never-seen/debug")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "rid_not_found"


@pytest.mark.asyncio
async def test_oversized_page_size_returns_400(client) -> None:
    c, _ = client
    resp = await c.get("/requests/rid-1/debug?page_size=10000")
    assert resp.status_code == 400
