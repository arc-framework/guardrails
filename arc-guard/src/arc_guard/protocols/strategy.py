"""ActionStrategy protocol — decides how to transform text given findings."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from arc_guard.types import Finding


@runtime_checkable
class ActionStrategy(Protocol):
    """Transforms text based on the findings produced by inspectors.

    The pipeline resolves the active strategy from FlagProvider.get_string("action_strategy").
    Default: "redact".
    """

    def apply(
        self, text: str, findings: tuple[Finding, ...]
    ) -> tuple[str, Literal["pass", "redact", "hash", "block"]]:
        """Apply the strategy to *text* using *findings* to locate spans.

        Returns:
            A tuple of (transformed_text, action_label).
        """
        ...
