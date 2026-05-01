from __future__ import annotations

from typing import Literal

from arc_guard_core.types import Finding


class BlockStrategy:
    """Blocks all output by returning an empty string regardless of findings."""

    def apply(self, text: str, findings: tuple[Finding, ...]) -> tuple[str, Literal["block"]]:
        """Return an empty string with action label ``"block"``."""
        return ("", "block")
