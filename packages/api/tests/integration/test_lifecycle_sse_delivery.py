"""Integration: live SSE delivery — broadcast → subscriber queue → SSE wire format.

We test the data path WITHOUT going through `httpx.ASGITransport` because
ASGITransport buffers infinite streaming responses badly (known compatibility
issue between httpx in-process ASGI client and `StreamingResponse` generators
that don't quickly close). Instead we drive the moving parts directly:

  pipeline → BroadcastingLifecycleSink → SubscriberRegistry queue → SSE generator

Together with `test_lifecycle_transport_emission.py` (which tests the data
side via the in-memory ring buffer query path) this covers the full live
delivery contract: events get emitted, queues see them, and the SSE
generator formats them per the contract in `contracts/http-events-sse.md`.

A real end-to-end SSE consumer test using uvicorn-in-subprocess is left to
a future smoke-suite; it's covered today by manual `curl -N /events` against
`make docker-up`.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from typing import Any

import pytest
from arc_guard_core.lifecycle import (
    RequestStarted,
    new_event_id,
)

from arc_guard_service.transport.events import (
    BroadcastingLifecycleSink,
    SubscriberRegistry,
    _event_to_json_dict,
    build_events_router,
)


def _evt_request_started(rid: str, seq: int = 0) -> RequestStarted:
    return RequestStarted(
        id=new_event_id(),
        parent_id=None,
        seq=seq,
        ts=datetime.now(UTC),
        rid=rid,
        route="/v1/chat/completions",
        model="demo",
        msg_count=1,
        input_size_bytes=42,
    )


@pytest.mark.asyncio
async def test_broadcaster_satisfies_lifecyclesink_protocol() -> None:
    from arc_guard_core.lifecycle import LifecycleSink

    registry = SubscriberRegistry()
    sink = BroadcastingLifecycleSink(registry)
    assert isinstance(sink, LifecycleSink)


@pytest.mark.asyncio
async def test_broadcast_delivers_to_single_subscriber() -> None:
    registry = SubscriberRegistry(queue_capacity=10)
    queue = await registry.register()
    assert registry.subscriber_count == 1

    sink = BroadcastingLifecycleSink(registry)
    ev = _evt_request_started("rid-1")
    await sink.emit(ev)

    received = await asyncio.wait_for(queue.get(), timeout=0.5)
    assert received is ev
    assert received.rid == "rid-1"

    await registry.unregister(queue)
    assert registry.subscriber_count == 0


@pytest.mark.asyncio
async def test_broadcast_delivers_to_every_subscriber() -> None:
    registry = SubscriberRegistry(queue_capacity=10)
    q1 = await registry.register()
    q2 = await registry.register()
    q3 = await registry.register()

    sink = BroadcastingLifecycleSink(registry)
    ev = _evt_request_started("fan-out-rid")
    await sink.emit(ev)

    for q in (q1, q2, q3):
        got = await asyncio.wait_for(q.get(), timeout=0.5)
        assert got is ev


@pytest.mark.asyncio
async def test_full_subscriber_queue_drops_oldest_not_newest() -> None:
    """When a subscriber's queue is full, drop the OLDEST event in their
    queue and enqueue the new one. Per-subscriber drop counter increments."""
    registry = SubscriberRegistry(queue_capacity=2)
    queue = await registry.register()

    sink = BroadcastingLifecycleSink(registry)
    e1 = _evt_request_started("rid-1", seq=1)
    e2 = _evt_request_started("rid-2", seq=2)
    e3 = _evt_request_started("rid-3", seq=3)
    e4 = _evt_request_started("rid-4", seq=4)

    await sink.emit(e1)
    await sink.emit(e2)
    # Queue is now full at capacity 2.
    assert registry.dropped_per_subscriber_total == 0
    await sink.emit(e3)
    await sink.emit(e4)
    # Two drops should have happened (one per overflow emission).
    assert registry.dropped_per_subscriber_total == 2

    # Newest two events remain in the queue, oldest two were dropped.
    first = await asyncio.wait_for(queue.get(), timeout=0.5)
    second = await asyncio.wait_for(queue.get(), timeout=0.5)
    assert first is e3
    assert second is e4


@pytest.mark.asyncio
async def test_event_to_json_dict_carries_universal_envelope_fields() -> None:
    """The wire-format helper preserves id/parent_id/seq/ts/rid + event_type
    discriminator + tuples-as-lists per `contracts/lifecycle-event-types.md`."""
    ev = _evt_request_started("envelope-test")
    d = _event_to_json_dict(ev)

    for required in ("id", "parent_id", "seq", "ts", "rid", "event_type"):
        assert required in d, f"missing universal field {required!r}"
    assert d["event_type"] == "RequestStarted"
    assert d["rid"] == "envelope-test"
    assert isinstance(d["ts"], str)  # ISO 8601 string, JSON-serializable
    # JSON round-trip must succeed.
    json.dumps(d)


@pytest.mark.asyncio
async def test_event_to_json_dict_coerces_tuples_to_lists() -> None:
    """`FindingProduced.span` is a tuple in Python; must serialize as a JSON list."""
    from arc_guard_core.lifecycle import FindingProduced

    ev = FindingProduced(
        id=new_event_id(),
        parent_id="parent",
        seq=1,
        ts=datetime.now(UTC),
        rid="span-test",
        entity_type="EMAIL_ADDRESS",
        span=(12, 29),
        score=1.0,
        risk_level=3,
        inspector="presidio",
    )
    d = _event_to_json_dict(ev)
    assert d["span"] == [12, 29]
    assert isinstance(d["span"], list)
    raw = json.dumps(d)
    assert "[12, 29]" in raw


@pytest.mark.asyncio
async def test_sse_generator_yields_well_formed_messages() -> None:
    """Drive the SSE generator manually and verify the chunks it emits match
    the wire format documented in `contracts/http-events-sse.md`:

        event: lifecycle\\n
        id: <ULID>\\n
        data: <JSON>\\n\\n
    """
    registry = SubscriberRegistry(queue_capacity=10)
    router = build_events_router(registry=registry, heartbeat_seconds=10.0)
    # Find the route handler we just registered.
    route = next(r for r in router.routes if getattr(r, "path", None) == "/events")
    handler = route.endpoint

    # The handler returns a StreamingResponse; we can drive its body iterator
    # by calling the inner async generator. Easier: register a queue, broadcast,
    # then call the handler to get the response, then iterate its body.
    sink = BroadcastingLifecycleSink(registry)
    ev = _evt_request_started("gen-test")
    # Build the response BEFORE emitting so the subscriber is registered first.

    # Pump the SSE handler in a background task; we read its yielded chunks.
    response = await handler()
    body_iter = response.body_iterator

    # The very first chunk should be the connection-open comment so headers
    # and first byte arrive together.
    first = await asyncio.wait_for(_anext(body_iter), timeout=0.5)
    assert first.strip() == ":" + " connected", first

    # Now emit a real event and verify the generator yields it.
    await sink.emit(ev)
    chunk = await asyncio.wait_for(_anext(body_iter), timeout=0.5)
    assert chunk.startswith("event: lifecycle\n"), chunk
    assert "data: " in chunk
    # Extract the data line and round-trip the JSON.
    m = re.search(r"data: (\{.*\})\n", chunk, re.DOTALL)
    assert m is not None, chunk
    payload = json.loads(m.group(1))
    assert payload["event_type"] == "RequestStarted"
    assert payload["rid"] == "gen-test"

    # Cleanly close the generator so we don't leak the background loop.
    await body_iter.aclose()


async def _anext(it: Any) -> Any:
    """Async-iterator next() shim — works on FastAPI's body_iterator."""
    return await it.__anext__()
