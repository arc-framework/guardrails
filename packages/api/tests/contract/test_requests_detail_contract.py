"""Contract: ``GET /requests/{rid}`` workspace manifest envelope shape."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink
from arc_guard_core.schemas import RequestWorkspaceManifest

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


def _seed_summary(path: str, rid: str, *, live: bool = False) -> None:
    conn = sqlite3.connect(path)
    started = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC).isoformat()
    try:
        conn.execute(
            "INSERT INTO request_summaries"
            " (rid, started_at, last_event_at, status, final_action,"
            "  max_risk, duration_ms, decision_id, live, stage)"
            " VALUES (?, ?, ?, ?, 'pass', 0.1, 50, NULL, ?, 'report')",
            (rid, started, started, "live" if live else "completed", 1 if live else 0),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
async def client(tmp_path: Path):
    db = tmp_path / "arc_guardrail.db"
    SqliteLifecycleSink(str(db))
    settings = ServiceSettings(
        enable_chat_completions=False, lifecycle_sqlite_path=str(db)
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as c:
        yield c, str(db)


@pytest.mark.asyncio
async def test_returns_manifest_with_links(client) -> None:
    c, db = client
    _seed_summary(db, "01JABC0EVT01")
    resp = await c.get("/requests/01JABC0EVT01")
    assert resp.status_code == 200
    manifest = RequestWorkspaceManifest.model_validate(resp.json())
    assert manifest.summary.rid == "01JABC0EVT01"
    assert manifest.links.lifecycle == "/lifecycle/01JABC0EVT01"
    assert manifest.links.decision == "/requests/01JABC0EVT01/decision"
    assert manifest.links.debug == "/requests/01JABC0EVT01/debug"
    assert manifest.links.live_stream == "/events?rid=01JABC0EVT01"


@pytest.mark.asyncio
async def test_resources_decision_and_debug_false_when_absent(client) -> None:
    c, db = client
    _seed_summary(db, "01JABC0EVT01")
    resp = await c.get("/requests/01JABC0EVT01")
    manifest = RequestWorkspaceManifest.model_validate(resp.json())
    assert manifest.resources.lifecycle is True
    assert manifest.resources.decision is False
    assert manifest.resources.debug is False
    assert manifest.resources.live_stream is False


@pytest.mark.asyncio
async def test_live_stream_mirrors_summary_live(client) -> None:
    c, db = client
    _seed_summary(db, "01JABC0EVT01", live=True)
    resp = await c.get("/requests/01JABC0EVT01")
    manifest = RequestWorkspaceManifest.model_validate(resp.json())
    assert manifest.summary.live is True
    assert manifest.resources.live_stream is True


@pytest.mark.asyncio
async def test_unknown_rid_returns_404(client) -> None:
    c, _ = client
    resp = await c.get("/requests/never-seen")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "rid_not_found"


@pytest.mark.asyncio
async def test_malformed_rid_returns_400(client) -> None:
    c, _ = client
    resp = await c.get("/requests/has spaces")
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["code"] == "rid_malformed"
