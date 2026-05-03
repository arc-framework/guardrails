"""Live SSE endpoint + supporting subscriber registry and broadcasting sink.

Three classes coordinate live event delivery:

1. `SubscriberRegistry` — tracks per-subscriber bounded queues; broadcast
   enqueues each event to every subscriber's queue with per-queue
   drop-oldest under back-pressure.
2. `BroadcastingLifecycleSink` — implements `LifecycleSink`; `emit` calls
   `registry.broadcast(event)`; `query` returns None (broadcast-only).
3. `build_events_router(registry, settings)` — FastAPI router exposing
   `GET /events` as a `text/event-stream` response. Per-connection
   subscriber lifecycle is managed inside the streaming generator.
"""

import asyncio
import importlib
import logging
import time
from contextlib import suppress
from dataclasses import asdict
from datetime import datetime
from typing import Any

from arc_guard_core.lifecycle import LifecycleEvent

_LOG = logging.getLogger("arc-guard.api.events")

_HEARTBEAT_SECONDS = 15.0


def _event_to_json_dict(event: LifecycleEvent) -> dict[str, Any]:
    """Serialize a LifecycleEvent dataclass to a JSON-friendly dict.

    `dataclasses.asdict` recurses into nested dataclasses; we coerce
    `datetime` → ISO 8601 string and `tuple` → list at the top level.
    """
    d = asdict(event)
    # event_type is a ClassVar so asdict doesn't include it; add it as the
    # discriminator wire field.
    d["event_type"] = type(event).event_type
    for k, v in list(d.items()):
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif isinstance(v, tuple):
            d[k] = list(v)
    return d


class SubscriberRegistry:
    """Tracks live SSE subscribers; manages per-subscriber bounded queues."""

    def __init__(self, queue_capacity: int = 1000) -> None:
        self._queue_capacity = queue_capacity
        self._subscribers: set[asyncio.Queue[LifecycleEvent | None]] = set()
        self._lock = asyncio.Lock()
        self._dropped_per_subscriber = 0

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @property
    def dropped_per_subscriber_total(self) -> int:
        return self._dropped_per_subscriber

    async def register(self) -> "asyncio.Queue[LifecycleEvent | None]":
        queue: asyncio.Queue[LifecycleEvent | None] = asyncio.Queue(
            maxsize=self._queue_capacity
        )
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unregister(
        self, queue: "asyncio.Queue[LifecycleEvent | None]"
    ) -> None:
        async with self._lock:
            self._subscribers.discard(queue)

    def broadcast(self, event: LifecycleEvent) -> None:
        """Synchronously enqueue to every subscriber. Non-blocking under
        back-pressure: when a subscriber's queue is full, the oldest event in
        THAT subscriber's queue is dropped (not the new event)."""
        if not self._subscribers:
            return
        for queue in tuple(self._subscribers):  # snapshot for safe iteration
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest in this subscriber's queue; enqueue new event.
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                self._dropped_per_subscriber += 1
                with suppress(asyncio.QueueFull):
                    queue.put_nowait(event)

    def shutdown(self) -> None:
        """Signal every active subscriber to terminate by enqueuing a sentinel."""
        for queue in tuple(self._subscribers):
            with suppress(asyncio.QueueFull):
                queue.put_nowait(None)


class BroadcastingLifecycleSink:
    """LifecycleSink Protocol impl that fans events into a SubscriberRegistry.

    `emit` is non-blocking — `broadcast` enqueues without awaiting downstream
    consumers. `query` returns None (this sink is broadcast-only; pair with
    `RingBufferLifecycleSink` in a Composite for replay support).
    """

    def __init__(self, registry: SubscriberRegistry) -> None:
        self._registry = registry

    async def emit(self, event: LifecycleEvent) -> None:
        self._registry.broadcast(event)

    async def query(self, rid: str) -> list[LifecycleEvent] | None:
        return None

    async def close(self) -> None:
        self._registry.shutdown()


def build_events_router(
    *,
    registry: SubscriberRegistry,
    heartbeat_seconds: float = _HEARTBEAT_SECONDS,
) -> Any:
    """Construct a FastAPI router exposing `GET /events` as SSE."""
    fastapi = importlib.import_module("fastapi")
    StreamingResponse = fastapi.responses.StreamingResponse  # noqa: N806

    router = fastapi.APIRouter()

    @router.get(
        "/events",
        summary="Live lifecycle event stream (Server-Sent Events)",
        tags=["lifecycle"],
        responses={
            200: {
                "description": "Server-Sent Events stream of typed lifecycle events",
                "content": {"text/event-stream": {}},
            }
        },
    )
    async def events_stream() -> Any:
        queue = await registry.register()

        async def generator() -> Any:
            # Flush a connection-open comment immediately so the upstream
            # consumer's response headers + first byte arrive without waiting
            # for the first event. SSE clients ignore comment lines (per
            # WHATWG spec), so this is purely a transport-level handshake.
            yield ": connected\n\n"
            last_heartbeat = time.monotonic()
            try:
                while True:
                    timeout = max(
                        0.1, heartbeat_seconds - (time.monotonic() - last_heartbeat)
                    )
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=timeout)
                    except asyncio.TimeoutError:
                        # Heartbeat to keep proxies from dropping the connection.
                        last_heartbeat = time.monotonic()
                        yield ": heartbeat\n\n"
                        continue
                    if event is None:  # shutdown sentinel
                        break
                    payload = _event_to_json_dict(event)
                    import json

                    data = json.dumps(payload, default=str)
                    yield f"event: lifecycle\nid: {event.id}\ndata: {data}\n\n"
                    last_heartbeat = time.monotonic()
            finally:
                await registry.unregister(queue)

        return StreamingResponse(
            generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return router


__all__ = [
    "SubscriberRegistry",
    "BroadcastingLifecycleSink",
    "build_events_router",
]
