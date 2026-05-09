"""In-memory `LifecycleSink` backed by `OrderedDict[rid, list[event]]`.

Bounded by `capacity` (number of distinct rids retained). When the buffer is
full and a new rid arrives, the oldest entire rid's events are evicted (rid-
level eviction; partial requests never appear). The dropped count is exposed
via `dropped_count`.

Lookup by `rid` is O(1).

Concurrency: events are produced from a single asyncio event loop; reads
(query, dropped_count) and writes (emit) are serialized through the loop. No
explicit lock is needed for typical single-loop deployments.
"""

from __future__ import annotations

from collections import OrderedDict

from arc_guard_core.lifecycle import LifecycleEvent


class RingBufferLifecycleSink:
    """LifecycleSink: bounded in-memory store, drop-oldest-rid on overflow."""

    def __init__(self, capacity: int = 5000) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._store: OrderedDict[str, list[LifecycleEvent]] = OrderedDict()
        self._dropped_count = 0
        self._closed = False

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def dropped_count(self) -> int:
        """Number of evicted rids since construction. Each eviction drops one
        entire rid's worth of events (count of EVENTS dropped is not tracked
        separately; consumers wanting per-event accounting should subscribe to
        the live SSE stream)."""
        return self._dropped_count

    def __len__(self) -> int:
        return len(self._store)

    async def emit(self, event: LifecycleEvent) -> None:
        if self._closed:
            return
        rid = event.rid
        bucket = self._store.get(rid)
        if bucket is None:
            # New rid: ensure room first.
            if len(self._store) >= self._capacity:
                self._store.popitem(last=False)  # evict oldest rid
                self._dropped_count += 1
            bucket = []
            self._store[rid] = bucket
        else:
            # Touch: move this rid to the most-recent position.
            self._store.move_to_end(rid, last=True)
        bucket.append(event)

    async def query(self, rid: str) -> list[LifecycleEvent] | None:
        bucket = self._store.get(rid)
        if bucket is None:
            return None
        # Return a defensive copy ordered by `seq` ascending.
        return sorted(bucket, key=lambda e: e.seq)

    async def close(self) -> None:
        self._closed = True
        self._store.clear()


__all__ = ["RingBufferLifecycleSink"]
