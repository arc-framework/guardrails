"""Performance: dropped-rid counter is accurate within 0.1%.

Drives the ring buffer past its capacity with a known number of distinct
rids; asserts the sink's `dropped_count` exactly equals the number of
evictions implied by the (rids_emitted - capacity) arithmetic, within a
0.1% drift budget.

The contract is "drop-oldest at the rid level — partial requests never
appear in the lookup". This test is the spec-level guard that the
counter consumers see on the metrics dashboard is a faithful proxy for
the actual eviction count.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from arc_guard.observability.ring_buffer_lifecycle_sink import RingBufferLifecycleSink
from arc_guard_core.lifecycle import RequestStarted, new_event_id

pytestmark = pytest.mark.slow

_CAPACITY = 1_000
_TOTAL_RIDS = 25_000
_TOLERANCE_PERCENT = 0.001  # 0.1%


def _seed_event(rid: str, seq: int) -> RequestStarted:
    return RequestStarted(
        id=new_event_id(),
        parent_id=None,
        seq=seq,
        ts=datetime.now(UTC),
        rid=rid,
        route="/v1/chat/completions",
        model="echo",
        msg_count=1,
        input_size_bytes=20,
    )


async def _flood(sink: RingBufferLifecycleSink, total: int) -> None:
    for i in range(total):
        await sink.emit(_seed_event(f"rid-{i:06d}", 0))


def test_dropped_rid_counter_matches_evictions_within_0_1_percent() -> None:
    sink = RingBufferLifecycleSink(capacity=_CAPACITY)

    asyncio.run(_flood(sink, _TOTAL_RIDS))

    expected_evictions = _TOTAL_RIDS - _CAPACITY
    actual_dropped = sink.dropped_count
    drift = abs(actual_dropped - expected_evictions) / expected_evictions

    print(
        f"\n[drop-counter] capacity={_CAPACITY} flooded={_TOTAL_RIDS} "
        f"expected_evictions={expected_evictions} actual_dropped={actual_dropped} "
        f"drift={drift * 100:.4f}%"
    )

    assert drift < _TOLERANCE_PERCENT, (
        f"dropped-rid counter drift {drift * 100:.4f}% exceeds "
        f"{_TOLERANCE_PERCENT * 100:.1f}% budget "
        f"(expected {expected_evictions}, got {actual_dropped})"
    )

    assert len(sink) == _CAPACITY, (
        f"ring buffer size after flood expected {_CAPACITY}, got {len(sink)}"
    )
