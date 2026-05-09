"""Contract: ``GET /requests/{rid}/decision`` envelope + 404/503 split."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink
from arc_guard_core.schemas import RequestDecisionEnvelope

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


def _seed_decision(
    path: str, rid: str, decision_id: str, payload: dict
) -> None:
    import json

    conn = sqlite3.connect(path)
    try:
        recorded = datetime(2026, 5, 9, 14, 0, 0, tzinfo=UTC).isoformat()
        body = json.dumps(payload)
        conn.execute(
            "INSERT INTO decision_records"
            " (rid, decision_id, recorded_at, payload_json, payload_size_bytes)"
            " VALUES (?, ?, ?, ?, ?)",
            (rid, decision_id, recorded, body, len(body)),
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
async def test_returns_envelope_when_present(client) -> None:
    c, db = client
    _seed_decision(db, "rid-1", "dec-XYZ", {"action": "block", "score": 0.9})
    resp = await c.get("/requests/rid-1/decision")
    assert resp.status_code == 200
    env = RequestDecisionEnvelope.model_validate(resp.json())
    assert env.rid == "rid-1"
    assert env.decision_id == "dec-XYZ"
    assert env.decision == {"action": "block", "score": 0.9}
    assert env.payload_size_bytes > 0


@pytest.mark.asyncio
async def test_404_when_decision_not_captured(client) -> None:
    c, _ = client
    resp = await c.get("/requests/rid-1/decision")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "decision_not_captured"


@pytest.mark.asyncio
async def test_503_when_sqlite_path_unset() -> None:
    settings = ServiceSettings(
        enable_chat_completions=False, lifecycle_sqlite_path=None
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as c:
        resp = await c.get("/requests/rid-1/decision")
    assert resp.status_code == 503
    assert "retry-after" in {k.lower() for k in resp.headers.keys()}


@pytest.mark.asyncio
async def test_malformed_rid_returns_400(client) -> None:
    c, _ = client
    resp = await c.get("/requests/has spaces/decision")
    assert resp.status_code == 400
