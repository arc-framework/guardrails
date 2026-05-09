"""End-to-end test: filtered SSE delivers per-rid live events + sentinel."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink
from arc_guard_core.lifecycle.events import (
    RequestCompleted,
    RequestStarted,
    StageRan,
)

from arc_guard_service.transport.events import SubscriberRegistry, build_events_router


@pytest.mark.asyncio
async def test_filter_drops_other_rids(tmp_path: Path) -> None:
    """A subscriber with ``?rid=X`` only receives events for X.

    Bounded by ``asyncio.wait_for`` so the test cannot wedge the loop if
    something goes wrong — it fails with a clear timeout error instead.
    """
    db = tmp_path / "arc_guardrail.db"
    sink = SqliteLifecycleSink(str(db))

    fastapi = __import__("fastapi")
    app = fastapi.FastAPI()
    registry = SubscriberRegistry()
    app.include_router(build_events_router(registry=registry, lifecycle_sink=sink))

    received_lines: list[str] = []

    async def _run() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=5.0) as c:
            ts = datetime(2026, 5, 9, 14, 0, 0, tzinfo=UTC)

            async def feed_events() -> None:
                # Wait until the subscriber is actually registered before
                # broadcasting — otherwise events are emitted to nobody.
                for _ in range(50):
                    if registry.subscriber_count > 0:
                        break
                    await asyncio.sleep(0.05)
                registry.broadcast(
                    RequestStarted(id="ev-1", parent_id=None, seq=1, ts=ts, rid="rid-other")
                )
                registry.broadcast(
                    RequestStarted(id="ev-2", parent_id=None, seq=1, ts=ts, rid="rid-target")
                )
                registry.broadcast(
                    StageRan(
                        id="ev-3",
                        parent_id="ev-2",
                        seq=2,
                        ts=ts,
                        rid="rid-target",
                        stage="classify",
                    )
                )
                registry.broadcast(
                    RequestCompleted(
                        id="ev-4",
                        parent_id="ev-2",
                        seq=3,
                        ts=ts,
                        rid="rid-target",
                        blocked=False,
                        pre_action="pass",
                        total_duration_ms=15.0,
                    )
                )

            feeder = asyncio.create_task(feed_events())
            try:
                async with c.stream("GET", "/events?rid=rid-target") as resp:
                    assert resp.status_code == 200
                    async for line in resp.aiter_lines():
                        received_lines.append(line)
                        if "terminated" in line:
                            break
            finally:
                feeder.cancel()

    try:
        await asyncio.wait_for(_run(), timeout=10.0)
    finally:
        await sink.close()

    rids_seen = set()
    for line in received_lines:
        if line.startswith("data:"):
            body = json.loads(line[len("data:") :].strip())
            rid_field = body.get("rid")
            if rid_field is not None:
                rids_seen.add(rid_field)
    assert rids_seen == {"rid-target"}


@pytest.mark.asyncio
async def test_already_terminated_rid_returns_immediate_sentinel(
    tmp_path: Path,
) -> None:
    """Subscribing after RequestCompleted yields the sentinel + close, no
    replay of historical events."""
    db = tmp_path / "arc_guardrail.db"
    sink = SqliteLifecycleSink(str(db))
    ts = datetime(2026, 5, 9, 14, 0, 0, tzinfo=UTC)
    body = ""
    try:
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

        fastapi = __import__("fastapi")
        app = fastapi.FastAPI()
        registry = SubscriberRegistry()
        app.include_router(build_events_router(registry=registry, lifecycle_sink=sink))

        async def _run() -> str:
            transport = httpx.ASGITransport(app=app)
            buf = ""
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test", timeout=5.0
            ) as c:
                async with c.stream("GET", "/events?rid=rid-done") as resp:
                    assert resp.status_code == 200
                    async for chunk in resp.aiter_text():
                        buf += chunk
                        if "terminated" in buf:
                            break
            return buf

        body = await asyncio.wait_for(_run(), timeout=10.0)
    finally:
        await sink.close()

    # The historical RequestStarted / RequestCompleted are NOT replayed;
    # only the sentinel appears.
    assert "event: terminated" in body
    assert "already_completed" in body
    # No `event: lifecycle` lines should appear.
    assert "event: lifecycle" not in body
