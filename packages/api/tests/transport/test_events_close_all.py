"""``POST /events/close-all`` shutdowns every active SSE subscriber.

Operator escape hatch for stuck SSE connections: enqueues a shutdown
sentinel into every subscriber's queue. Subscriber generators detect
the ``None`` sentinel, exit their loop, and unregister cleanly on the
next event-loop tick.
"""

from __future__ import annotations

import asyncio

import pytest

from arc_guard_service.transport.events import (
    SubscriberRegistry,
    build_events_router,
)


@pytest.mark.asyncio
async def test_close_all_signals_every_subscriber() -> None:
    registry = SubscriberRegistry(queue_capacity=10)
    # Register three live subscribers — each holds an asyncio.Queue.
    q1 = await registry.register()
    q2 = await registry.register()
    q3 = await registry.register()
    assert registry.subscriber_count == 3

    router = build_events_router(registry=registry, lifecycle_sink=None)
    handler = next(
        r for r in router.routes if getattr(r, "path", "") == "/events/close-all"
    )
    response = await handler.endpoint()  # type: ignore[no-untyped-call]

    # JSONResponse — body is bytes containing the JSON dict.
    import json

    body = json.loads(response.body)
    assert body["closed"] == 3
    # The shutdown signal is enqueued synchronously; subscriber count
    # only drops after each generator hits its ``finally``. We assert
    # the sentinel landed in every queue:
    for q in (q1, q2, q3):
        item = await asyncio.wait_for(q.get(), timeout=0.5)
        assert item is None, "expected shutdown sentinel"


@pytest.mark.asyncio
async def test_close_all_with_zero_subscribers_is_a_noop() -> None:
    registry = SubscriberRegistry(queue_capacity=10)
    router = build_events_router(registry=registry, lifecycle_sink=None)
    handler = next(
        r for r in router.routes if getattr(r, "path", "") == "/events/close-all"
    )
    response = await handler.endpoint()  # type: ignore[no-untyped-call]
    import json

    body = json.loads(response.body)
    assert body["closed"] == 0
    assert body["remaining_after_signal"] == 0
