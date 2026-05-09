"""Middleware protocol — pre/post hooks around the pipeline."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from arc_guard_core.types import GuardInput, GuardResult


@runtime_checkable
class Middleware(Protocol):
    """Wraps the pipeline with before/after hooks.

    Concurrency: both. The pipeline calls whichever pair matches the active
    mode (sync vs async).
    Thread-safety: thread-safe.

    Declared exceptions: implementation-specific subclasses of ``AdapterError``.

    Failure mode: open. Middleware failures are logged via the ``Logger``
    hook; the pipeline continues with the untouched input or result.
    """

    name: str

    def before(self, guard_input: GuardInput) -> GuardInput: ...

    def after(self, result: GuardResult) -> GuardResult: ...

    async def before_async(self, guard_input: GuardInput) -> GuardInput: ...

    async def after_async(self, result: GuardResult) -> GuardResult: ...
