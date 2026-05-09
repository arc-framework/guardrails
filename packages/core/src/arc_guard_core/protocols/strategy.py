"""ActionStrategy protocol — transforms text given findings."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from arc_guard_core.types import Finding, PolicyDecision


@runtime_checkable
class ActionStrategy(Protocol):
    """Transforms text based on inspector findings.

    Concurrency: sync. Implementations MUST be pure functions over their
    inputs — no IO, no logging, no event publishing.
    Thread-safety: thread-safe (no instance mutation).

    Declared exceptions: ``StrategyError``.

    Failure mode: closed. A broken strategy is not safe to swallow because
    the user-facing text may not have been transformed; the pipeline
    surfaces a ``RefusalEnvelope``.
    """

    name: str

    def apply(
        self, text: str, findings: Sequence[Finding]
    ) -> tuple[str, Sequence[PolicyDecision]]:
        """Return the transformed text and the per-finding decisions."""
        ...
