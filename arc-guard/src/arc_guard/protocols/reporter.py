"""Reporter protocol — fire-and-forget audit event sink."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from arc_guard.types import GuardResult


@runtime_checkable
class Reporter(Protocol):
    """Receives the final GuardResult for auditing or telemetry.

    Reporters MUST NOT raise — exceptions should be caught internally.
    The pipeline calls report() as a fire-and-forget coroutine; it does NOT
    await the full completion of delivery (e.g. NATS publish).
    """

    async def report(self, result: GuardResult) -> None:
        """Record or forward *result* for audit purposes."""
        ...
