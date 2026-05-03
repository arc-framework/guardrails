"""LifecycleSink Protocol — fifth observability surface for arc-guardrails.

Sinks receive every typed `LifecycleEvent` emitted by the pipeline and api
transport. Independent of the four existing observability Protocols
(`Reporter`, `Logger`, `MetricSink`, `Tracer`) — wired via a separate
constructor argument and failing independently.

Failure mode: open. Implementations MUST NOT propagate exceptions back into
the pipeline or transport. The orchestrator catches and counts.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from arc_guard_core.lifecycle.events import LifecycleEvent


@runtime_checkable
class LifecycleSink(Protocol):
    """Receives every typed LifecycleEvent emitted by the pipeline and api transport.

    Concurrency: async. Implementations MUST NOT block the calling pipeline.
    Thread-safety: implementations MUST be safe to call from any task in the
    asyncio event loop where the pipeline runs.
    Failure mode: open. Sink failures are logged and counted; they MUST NOT
    propagate back into the pipeline or the api transport.
    """

    async def emit(self, event: LifecycleEvent) -> None:
        """Receive one event for storage / forwarding / broadcast."""
        ...

    async def query(self, rid: str) -> list[LifecycleEvent] | None:
        """Return all events for `rid` ordered by `seq` ascending, or None if not found.

        Sinks that do not support lookup (e.g., a write-only forwarding sink)
        MUST return None for all rids.
        """
        ...

    async def close(self) -> None:
        """Release resources. Idempotent. MUST NOT raise."""
        ...


class NullLifecycleSink:
    """Discards every event; returns None for every query.

    Pipeline default. Constructing GuardPipeline without `lifecycle_hook=` gets
    this sink, ensuring zero behavioral change for operators not opting in.
    """

    async def emit(self, event: LifecycleEvent) -> None:
        return None

    async def query(self, rid: str) -> list[LifecycleEvent] | None:
        return None

    async def close(self) -> None:
        return None


__all__ = ["LifecycleSink", "NullLifecycleSink"]
