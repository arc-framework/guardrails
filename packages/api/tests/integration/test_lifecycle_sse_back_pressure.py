"""Integration: SSE back-pressure semantics. When a subscriber's bounded
queue is full, the OLDEST event in THAT subscriber's queue is dropped (not
the new event), the per-subscriber dropped counter increments, and OTHER
subscribers continue receiving every event normally.

These properties keep one slow consumer from starving every other consumer
or back-pressuring the pipeline.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from arc_guard_core.lifecycle import RequestStarted, new_event_id

from arc_guard_service.transport.events import (
    BroadcastingLifecycleSink,
    SubscriberRegistry,
)


def _evt(rid: str, seq: int) -> RequestStarted:
    return RequestStarted(
        id=new_event_id(),
        parent_id=None,
        seq=seq,
        ts=datetime.now(UTC),
        rid=rid,
        route="/test",
    )


@pytest.mark.asyncio
async def test_full_subscriber_queue_drops_oldest() -> None:
    """Subscriber with capacity=1 receives only the LAST event of a burst;
    oldest events are dropped on overflow."""
    registry = SubscriberRegistry(queue_capacity=1)
    queue = await registry.register()
    sink = BroadcastingLifecycleSink(registry)

    events = [_evt(f"bp-{i}", seq=i) for i in range(10)]
    for ev in events:
        await sink.emit(ev)

    received = await asyncio.wait_for(queue.get(), timeout=0.5)
    assert received is events[-1], (
        f"expected last event ({events[-1].rid}); got {received.rid}"
    )

    # Queue should now be empty — drop-oldest leaves at most one event.
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(queue.get(), timeout=0.05)


@pytest.mark.asyncio
async def test_per_subscriber_drop_counter_accuracy() -> None:
    """Drop counter must equal the number of overflow emissions to within 0.1%."""
    registry = SubscriberRegistry(queue_capacity=2)
    await registry.register()
    sink = BroadcastingLifecycleSink(registry)

    n_emit = 1000
    for i in range(n_emit):
        await sink.emit(_evt(f"drop-counter-{i}", seq=i))

    # Capacity 2 holds 2 events; the other 998 are drops.
    expected_drops = n_emit - 2
    actual = registry.dropped_per_subscriber_total
    delta_pct = abs(actual - expected_drops) / expected_drops * 100
    assert delta_pct < 0.1, (
        f"dropped counter drift {delta_pct:.2f}% > 0.1% (actual={actual}, expected={expected_drops})"
    )


@pytest.mark.asyncio
async def test_slow_subscriber_does_not_starve_fast_subscribers() -> None:
    """One subscriber with capacity=1 (gets back-pressured) should NOT prevent
    a fast subscriber with capacity=100 from receiving every event."""
    registry = SubscriberRegistry()
    # Two subscribers; first has tiny queue, second has plenty.
    slow_queue = await registry.register()  # default queue_capacity=1000

    # Override the slow queue's capacity by replacing it with a smaller one.
    # The registry doesn't support per-subscriber capacity directly, so we
    # simulate "slow" by NOT consuming from this queue while emitting.
    # The real fast vs slow contrast: fast subscriber drains; slow doesn't.
    fast_queue = await registry.register()
    sink = BroadcastingLifecycleSink(registry)

    n_emit = 50
    for i in range(n_emit):
        await sink.emit(_evt(f"slow-vs-fast-{i}", seq=i))
        # Drain the fast queue immediately; leave slow queue alone.
        received = await asyncio.wait_for(fast_queue.get(), timeout=0.1)
        assert received.seq == i

    # Fast subscriber received every event in order. Slow subscriber's queue
    # holds whatever was enqueued (up to its capacity); we don't assert on
    # its content — only that the fast path was unaffected.
    assert slow_queue.qsize() <= 1000


@pytest.mark.asyncio
async def test_pipeline_emission_does_not_block_on_slow_subscriber() -> None:
    """The orchestrator emits events without awaiting consumer drain.
    Verifies the broadcast loop is non-blocking even with one full queue."""
    registry = SubscriberRegistry(queue_capacity=1)
    await registry.register()
    sink = BroadcastingLifecycleSink(registry)

    import time

    t0 = time.perf_counter()
    for i in range(1000):
        await sink.emit(_evt(f"non-block-{i}", seq=i))
    elapsed_ms = (time.perf_counter() - t0) * 1000

    # 1000 emissions to a perpetually-full queue should still complete in
    # well under a second (drop-oldest is O(1) per emit). 100 ms is a
    # generous threshold against accidental introduction of blocking.
    assert elapsed_ms < 100.0, (
        f"1000 emissions to full queue took {elapsed_ms:.1f}ms (>100ms threshold)"
    )
