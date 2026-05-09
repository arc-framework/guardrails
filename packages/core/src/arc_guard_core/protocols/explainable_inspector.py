"""Optional Inspector capability: surface match explanations for findings."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from arc_guard_core.types import Finding


@dataclass(frozen=True)
class InspectorMatchExplanation:
    """One explanation record for a finding produced by an inspector.

    Pipelines emit one ``InspectorMatchExplain`` lifecycle event per record.
    """

    finding: Finding
    pattern_id: str
    explanation: str | None = None


@runtime_checkable
class ExplainableInspector(Protocol):
    """Optional capability: an inspector that can surface match metadata.

    Implementations are stateless — the pipeline calls ``explain_matches``
    with the text and the new findings the inspector just produced, and
    receives back zero or more explanation records.
    """

    def explain_matches(
        self, text: str, new_findings: Sequence[Finding]
    ) -> list[InspectorMatchExplanation]:
        ...


__all__ = ["ExplainableInspector", "InspectorMatchExplanation"]
