"""Inspector protocol — one detection step in the pipeline."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from arc_guard_core.types import GuardResult


@runtime_checkable
class Inspector(Protocol):
    """A single detection step in the guard pipeline.

    Concurrency: sync. The pipeline may invoke an inspector from any thread.
    Implementations MUST NOT mutate instance state across calls.
    Thread-safety: thread-safe (no instance mutation).

    Declared exceptions: ``InspectorError``. The pipeline catches and wraps
    other exceptions into ``InspectorError``.

    Failure mode: open. An ``InspectorError`` causes the pipeline to record
    ``bypass_reason="error"`` and continue with the prior result.
    """

    name: str

    def inspect(self, result: GuardResult) -> GuardResult:
        """Inspect the text in *result* and return an updated GuardResult.

        Implementations should produce a new GuardResult with additional
        findings appended rather than mutating the input.
        """
        ...
