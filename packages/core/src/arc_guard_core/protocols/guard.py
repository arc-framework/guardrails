"""Guard protocol — top-level entry point for the pipeline."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from arc_guard_core.types import GuardInput, GuardResult


@runtime_checkable
class Guard(Protocol):
    """Top-level guard interface.

    Concurrency: both. ``pre_process`` and ``post_process`` are async; the
    ``*_sync`` variants are synchronous wrappers for callers that cannot
    await. Implementations MUST be thread-safe — the pipeline may be invoked
    from multiple threads or coroutines simultaneously.

    Declared exceptions: none. Failures MUST surface as a ``GuardResult``
    (with ``bypass_reason="error"`` for fail-open paths or ``action="block"``
    with a ``RefusalEnvelope`` for fail-closed paths). FR-023 forbids
    unwrapped exceptions across this boundary.

    Failure mode: aggregate fail-open. Each underlying stage carries its
    own per-stage mode (see ``contracts/exceptions.md``).
    """

    async def pre_process(self, guard_input: GuardInput) -> GuardResult: ...

    async def post_process(self, guard_input: GuardInput) -> GuardResult: ...

    def pre_process_sync(self, guard_input: GuardInput) -> GuardResult: ...

    def post_process_sync(self, guard_input: GuardInput) -> GuardResult: ...
