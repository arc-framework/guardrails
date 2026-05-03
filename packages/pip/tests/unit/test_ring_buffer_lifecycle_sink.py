"""Unit tests for `RingBufferLifecycleSink`: capacity, drop-oldest, dropped
counter accuracy, O(1) lookup, idempotent close.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from arc_guard.observability.ring_buffer_lifecycle_sink import RingBufferLifecycleSink
from arc_guard_core.lifecycle import (
    LifecycleSink,
    RequestStarted,
    StageRan,
    new_event_id,
)


def _evt(rid: str, seq: int) -> RequestStarted | StageRan:
    cls = RequestStarted if seq == 0 else StageRan
    return cls(
        id=new_event_id(),
        parent_id=None,
        seq=seq,
        ts=datetime.now(timezone.utc),
        rid=rid,
    )


def test_satisfies_lifecycle_sink_protocol() -> None:
    assert isinstance(RingBufferLifecycleSink(), LifecycleSink)


def test_emit_and_query_round_trip() -> None:
    sink = RingBufferLifecycleSink(capacity=10)
    asyncio.run(sink.emit(_evt("a", 0)))
    asyncio.run(sink.emit(_evt("a", 1)))
    asyncio.run(sink.emit(_evt("a", 2)))
    result = asyncio.run(sink.query("a"))
    assert result is not None
    assert len(result) == 3
    assert [e.seq for e in result] == [0, 1, 2]


def test_query_unknown_rid_returns_none() -> None:
    sink = RingBufferLifecycleSink(capacity=10)
    assert asyncio.run(sink.query("never-emitted")) is None


def test_drop_oldest_rid_when_capacity_exceeded() -> None:
    sink = RingBufferLifecycleSink(capacity=3)

    async def populate() -> None:
        for rid in ["a", "b", "c", "d", "e"]:
            await sink.emit(_evt(rid, 0))

    asyncio.run(populate())

    # Capacity is 3 → 2 rids evicted (a, b)
    assert sink.dropped_count == 2
    assert asyncio.run(sink.query("a")) is None
    assert asyncio.run(sink.query("b")) is None
    assert asyncio.run(sink.query("c")) is not None
    assert asyncio.run(sink.query("d")) is not None
    assert asyncio.run(sink.query("e")) is not None


def test_dropped_count_zero_when_within_capacity() -> None:
    sink = RingBufferLifecycleSink(capacity=10)
    for i in range(5):
        asyncio.run(sink.emit(_evt(f"rid-{i}", 0)))
    assert sink.dropped_count == 0


def test_re_emitting_existing_rid_does_not_evict() -> None:
    """Adding more events to an existing rid bucket must not count against
    capacity (only distinct rids consume capacity)."""
    sink = RingBufferLifecycleSink(capacity=2)
    asyncio.run(sink.emit(_evt("a", 0)))
    asyncio.run(sink.emit(_evt("a", 1)))
    asyncio.run(sink.emit(_evt("a", 2)))
    asyncio.run(sink.emit(_evt("b", 0)))
    asyncio.run(sink.emit(_evt("b", 1)))
    assert sink.dropped_count == 0
    assert len(asyncio.run(sink.query("a"))) == 3
    assert len(asyncio.run(sink.query("b"))) == 2


def test_emit_promotes_rid_to_most_recent() -> None:
    """Touching an existing rid moves it to the back of the LRU; older
    rids that haven't been touched are evicted first."""
    sink = RingBufferLifecycleSink(capacity=2)
    asyncio.run(sink.emit(_evt("a", 0)))
    asyncio.run(sink.emit(_evt("b", 0)))
    asyncio.run(sink.emit(_evt("a", 1)))  # touch 'a'; 'b' is now oldest
    asyncio.run(sink.emit(_evt("c", 0)))  # should evict 'b'
    assert asyncio.run(sink.query("a")) is not None
    assert asyncio.run(sink.query("b")) is None
    assert asyncio.run(sink.query("c")) is not None


def test_close_is_idempotent_and_drops_state() -> None:
    sink = RingBufferLifecycleSink(capacity=10)
    asyncio.run(sink.emit(_evt("a", 0)))
    asyncio.run(sink.close())
    asyncio.run(sink.close())  # second call must not raise
    assert asyncio.run(sink.query("a")) is None


def test_capacity_must_be_positive() -> None:
    with pytest.raises(ValueError):
        RingBufferLifecycleSink(capacity=0)
