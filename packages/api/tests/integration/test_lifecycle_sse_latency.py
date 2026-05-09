"""Integration: live SSE delivery latency. Verifies the documented contract
that p95 emit-to-consumer wall-clock is below 100 ms when the consumer is
keeping up.

Bypasses the HTTP layer (httpx ASGITransport doesn't play nice with infinite
SSE generators in-process) and measures registry → subscriber-queue latency
directly. This is the same data path the SSE generator drains; HTTP framing
adds < 1 ms in measured deployments.
"""

from __future__ import annotations

import asyncio
import statistics
import time
from datetime import UTC, datetime

import pytest
from arc_guard_core.lifecycle import RequestStarted, new_event_id

from arc_guard_service.transport.events import (
    BroadcastingLifecycleSink,
    SubscriberRegistry,
)


def _evt(rid: str, seq: int = 0) -> RequestStarted:
    return RequestStarted(
        id=new_event_id(),
        parent_id=None,
        seq=seq,
        ts=datetime.now(UTC),
        rid=rid,
        route="/test",
    )


@pytest.mark.asyncio
async def test_sse_emit_to_consumer_p95_under_100ms() -> None:
    """100-trial p95 latency from `BroadcastingLifecycleSink.emit(event)` to
    the subscriber queue receiving it. Must stay under 100 ms.

    This is a relaxed proxy for the spec's wall-clock measurement (which
    would include HTTP framing and network). The pure data-path latency in
    single-process Python should be sub-millisecond; the 100 ms threshold
    is a guardrail against pathological regressions (e.g., accidentally
    introducing a per-event sleep).
    """
    registry = SubscriberRegistry(queue_capacity=200)
    queue = await registry.register()
    sink = BroadcastingLifecycleSink(registry)

    latencies_ms: list[float] = []
    for i in range(100):
        ev = _evt(f"latency-{i}", seq=i)
        t0 = time.perf_counter()
        await sink.emit(ev)
        received = await asyncio.wait_for(queue.get(), timeout=0.5)
        latency_ms = (time.perf_counter() - t0) * 1000
        latencies_ms.append(latency_ms)
        assert received is ev

    p95 = sorted(latencies_ms)[int(0.95 * len(latencies_ms))]
    p50 = statistics.median(latencies_ms)
    print(f"\n[SSE latency] p50={p50:.3f}ms  p95={p95:.3f}ms  max={max(latencies_ms):.3f}ms")
    assert p95 < 100.0, f"p95 emit-to-consumer latency exceeded 100 ms threshold: {p95:.2f} ms"

    await registry.unregister(queue)


@pytest.mark.asyncio
async def test_sse_zero_subscribers_is_no_op() -> None:
    """Pipeline emission with NO subscribers must not block or allocate
    measurable time per event."""
    registry = SubscriberRegistry()
    sink = BroadcastingLifecycleSink(registry)

    t0 = time.perf_counter()
    for i in range(1000):
        await sink.emit(_evt(f"no-sub-{i}", seq=i))
    elapsed_ms = (time.perf_counter() - t0) * 1000
    per_event_us = (elapsed_ms / 1000) * 1000  # ms per event → µs
    print(f"\n[no-subscriber emit] 1000 events in {elapsed_ms:.2f}ms ({per_event_us:.1f} µs/event)")
    # Generous bound — should be sub-microsecond per event in practice.
    assert per_event_us < 100.0, (
        f"no-subscriber emit cost exceeded 100 µs/event: {per_event_us:.1f}"
    )
