"""Unit tests for `CompositeLifecycleSink`: fan-out, per-child failure
isolation, fall-through query, served-from tier label, idempotent close.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from arc_guard.observability.composite_lifecycle_sink import CompositeLifecycleSink
from arc_guard.observability.ring_buffer_lifecycle_sink import RingBufferLifecycleSink
from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink
from arc_guard_core.lifecycle import (
    LifecycleEvent,
    LifecycleSink,
    NullLifecycleSink,
    RequestStarted,
    new_event_id,
)


def _request_started(rid: str, seq: int = 0) -> RequestStarted:
    return RequestStarted(
        id=new_event_id(),
        parent_id=None,
        seq=seq,
        ts=datetime.now(timezone.utc),
        rid=rid,
        route="/test",
    )


class _RecordingSink:
    """Test sink that records every emit + query call. Used to assert
    fan-out semantics without depending on Ring/SQLite internals."""

    def __init__(self) -> None:
        self.emits: list[LifecycleEvent] = []
        self.queries: list[str] = []
        self.closed = False
        self.fail_on_emit = False
        self.fail_on_query = False

    async def emit(self, event: LifecycleEvent) -> None:
        if self.fail_on_emit:
            raise RuntimeError("simulated emit failure")
        self.emits.append(event)

    async def query(self, rid: str) -> list[LifecycleEvent] | None:
        self.queries.append(rid)
        if self.fail_on_query:
            raise RuntimeError("simulated query failure")
        return None

    async def close(self) -> None:
        self.closed = True


def test_satisfies_lifecycle_sink_protocol() -> None:
    composite = CompositeLifecycleSink([NullLifecycleSink()])
    assert isinstance(composite, LifecycleSink)


def test_requires_at_least_one_child() -> None:
    with pytest.raises(ValueError):
        CompositeLifecycleSink([])


def test_emit_fans_out_to_every_child() -> None:
    a = _RecordingSink()
    b = _RecordingSink()
    c = _RecordingSink()
    composite = CompositeLifecycleSink([a, b, c])

    ev = _request_started("fan-out")
    asyncio.run(composite.emit(ev))

    assert a.emits == [ev]
    assert b.emits == [ev]
    assert c.emits == [ev]


def test_emit_failure_in_one_child_does_not_block_siblings() -> None:
    a = _RecordingSink()
    b = _RecordingSink()
    b.fail_on_emit = True
    c = _RecordingSink()
    composite = CompositeLifecycleSink([a, b, c])

    ev = _request_started("isolation-test")
    asyncio.run(composite.emit(ev))

    assert a.emits == [ev]
    assert c.emits == [ev]
    assert composite.failures["_RecordingSink"] == 1


def test_emit_failure_count_increments_per_failure() -> None:
    a = _RecordingSink()
    a.fail_on_emit = True
    composite = CompositeLifecycleSink([a])

    asyncio.run(composite.emit(_request_started("rid-1")))
    asyncio.run(composite.emit(_request_started("rid-2")))
    asyncio.run(composite.emit(_request_started("rid-3")))

    assert composite.failures["_RecordingSink"] == 3


def test_query_returns_first_non_none_child_result() -> None:
    """Walk children in order; first hit wins."""
    a = RingBufferLifecycleSink(capacity=10)
    b = SqliteLifecycleSink(":memory:")
    composite = CompositeLifecycleSink([a, b])

    ev = _request_started("only-in-sqlite")
    # Skip the ring buffer; only emit to SQLite.
    asyncio.run(b.emit(ev))

    result = asyncio.run(composite.query("only-in-sqlite"))
    assert result is not None
    assert len(result) == 1
    assert composite.last_served_from == "sqlite"


def test_query_records_served_from_ring_buffer_when_ring_has_data() -> None:
    a = RingBufferLifecycleSink(capacity=10)
    b = SqliteLifecycleSink(":memory:")
    composite = CompositeLifecycleSink([a, b])

    ev = _request_started("in-ring-and-sqlite")
    asyncio.run(a.emit(ev))
    asyncio.run(b.emit(ev))

    result = asyncio.run(composite.query("in-ring-and-sqlite"))
    assert result is not None
    assert composite.last_served_from == "ring-buffer"


def test_query_returns_none_when_no_child_has_data() -> None:
    composite = CompositeLifecycleSink([
        RingBufferLifecycleSink(capacity=10),
        SqliteLifecycleSink(":memory:"),
    ])
    assert asyncio.run(composite.query("never-emitted")) is None
    assert composite.last_served_from == "composite-fallthrough"


def test_query_failure_in_one_child_falls_through_to_next() -> None:
    a = _RecordingSink()
    a.fail_on_query = True
    b = RingBufferLifecycleSink(capacity=10)
    composite = CompositeLifecycleSink([a, b])

    ev = _request_started("fallthrough-on-error")
    asyncio.run(b.emit(ev))

    result = asyncio.run(composite.query("fallthrough-on-error"))
    assert result is not None
    assert composite.failures["_RecordingSink"] == 1


def test_close_closes_every_child() -> None:
    a = _RecordingSink()
    b = _RecordingSink()
    c = _RecordingSink()
    composite = CompositeLifecycleSink([a, b, c])

    asyncio.run(composite.close())

    assert a.closed and b.closed and c.closed
