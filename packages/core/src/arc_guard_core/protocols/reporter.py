"""Reporter protocol — fire-and-forget audit event sink."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from arc_guard_core.types import GuardResult


@runtime_checkable
class Reporter(Protocol):
    """Receives the final ``GuardResult`` for auditing or telemetry.

    Concurrency: async. Implementations MUST NOT block the calling
    pipeline; the canonical pattern is a bounded ``asyncio.Queue`` with
    a background drain task.
    Thread-safety: thread-safe; queue access must be safe across producers.

    Declared exceptions: ``ReporterError``.

    Failure mode: open. Reporter failures are logged and counted via
    ``MetricSink``; they MUST NOT propagate back to the pipeline result.
    """

    async def report(self, result: GuardResult) -> None: ...

    async def close(self) -> None: ...
