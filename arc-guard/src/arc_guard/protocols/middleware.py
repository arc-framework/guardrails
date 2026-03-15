"""Middleware protocol — pre/post hooks around the full pipeline."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from arc_guard.types import GuardInput, GuardResult


@runtime_checkable
class Middleware(Protocol):
    """Wraps the pipeline with before/after hooks.

    Exception contract:
        If before() raises, the pipeline logs a warning and uses the original
        GuardInput unchanged (fail-open).
        If after() raises, the pipeline logs a warning and returns the
        pre-after() GuardResult unchanged (fail-open).
    """

    async def before(self, guard_input: GuardInput) -> GuardInput:
        """Called before inspectors run. May modify or enrich the input."""
        ...

    async def after(self, result: GuardResult) -> GuardResult:
        """Called after the strategy is applied. May enrich the result."""
        ...
