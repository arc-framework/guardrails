"""Guard protocol — top-level entry point for the pipeline."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from arc_guard.types import GuardInput, GuardResult


@runtime_checkable
class Guard(Protocol):
    """Top-level guard interface.

    Implementations receive a GuardInput and return a GuardResult.
    The pipeline distinguishes between pre-processing (user prompt) and
    post-processing (model response) via the context.source field.
    """

    async def pre_process(self, guard_input: GuardInput) -> GuardResult:
        """Inspect and optionally transform a user prompt before LLM inference."""
        ...

    async def post_process(self, guard_input: GuardInput) -> GuardResult:
        """Inspect and optionally transform the model response after inference."""
        ...
