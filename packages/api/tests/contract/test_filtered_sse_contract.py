"""Contract: ``GET /events?rid=<rid>`` filter wire format."""

from __future__ import annotations

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


@pytest.fixture()
async def app_and_sink(tmp_path: Path):
    db = tmp_path / "arc_guardrail.db"
    SqliteLifecycleSink(str(db))
    settings = ServiceSettings(enable_chat_completions=False, lifecycle_sqlite_path=str(db))
    app = create_app(settings)
    yield app, str(db)


@pytest.mark.asyncio
async def test_malformed_rid_returns_400(app_and_sink) -> None:
    app, _ = app_and_sink
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/events?rid=has spaces")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "rid_malformed"


@pytest.mark.asyncio
async def test_terminated_rid_immediate_sentinel(app_and_sink) -> None:
    """A rid known to have completed (per the sqlite tier) returns a
    ``terminated`` sentinel immediately, then closes."""
    app, db_path = app_and_sink
    # Pre-seed a RequestCompleted event for rid-done so the liveness check
    # finds it via lifecycle_sink.query().
    sink = SqliteLifecycleSink(db_path)
    try:
        ts = datetime(2026, 5, 9, 14, 0, 0, tzinfo=UTC)
        await sink.emit(RequestStarted(id="ev-1", parent_id=None, seq=1, ts=ts, rid="rid-done"))
        await sink.emit(
            RequestCompleted(
                id="ev-2",
                parent_id="ev-1",
                seq=2,
                ts=ts,
                rid="rid-done",
                blocked=False,
                pre_action="pass",
                total_duration_ms=10.0,
            )
        )
    finally:
        await sink.close()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        async with c.stream("GET", "/events?rid=rid-done") as resp:
            assert resp.status_code == 200
            body_chunks = []
            async for chunk in resp.aiter_text():
                body_chunks.append(chunk)
                if "terminated" in chunk:
                    break
            body = "".join(body_chunks)

    assert "event: terminated" in body
    assert '"rid": "rid-done"' in body or '"rid":"rid-done"' in body
    assert "already_completed" in body


# Note: the unfiltered ``GET /events`` firehose has no natural close, so
# testing it under ASGITransport without a body-consuming loop hangs the
# event loop. The unfiltered stream's contract is owned by the lifecycle-sink
# spec (010); spec 012 only adds the optional ``?rid=`` filter, and the two
# tests above cover both the malformed-rid and already-terminated branches.
