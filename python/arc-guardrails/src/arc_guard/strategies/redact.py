from __future__ import annotations

from typing import Literal

from arc_guard.types import Finding


class RedactStrategy:
    """Replaces each detected span with a bracketed entity-type label."""

    def apply(self, text: str, findings: tuple[Finding, ...]) -> tuple[str, Literal["redact"]]:
        """Replace spans in *text* with ``[ENTITY_TYPE]`` placeholders.

        Spans are replaced from right to left (sorted by start descending) so
        that earlier character offsets remain valid after each substitution.
        """
        if not findings:
            return (text, "redact")

        for finding in sorted(findings, key=lambda f: f.start, reverse=True):
            replacement = f"[{finding.entity_type}]"
            text = text[: finding.start] + replacement + text[finding.end :]

        return (text, "redact")
