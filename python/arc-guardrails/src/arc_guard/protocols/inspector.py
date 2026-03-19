"""Inspector protocol — one step in the Chain-of-Responsibility."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from arc_guard.types import GuardResult


@runtime_checkable
class Inspector(Protocol):
    """A single detection step in the guard pipeline.

    Inspectors receive the accumulated GuardResult and append new findings
    to it. Inspectors MUST NOT raise — they should catch exceptions internally
    and return the result unchanged on error.
    """

    async def inspect(self, result: GuardResult) -> GuardResult:
        """Inspect the text in *result* and return an updated GuardResult.

        Implementations should create a new GuardResult with additional
        findings appended rather than mutating the input.
        """
        ...
