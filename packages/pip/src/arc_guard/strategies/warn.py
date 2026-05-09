"""WarnStrategy — pass-through with a warning rationale."""

from __future__ import annotations

from collections.abc import Sequence

from arc_guard_core.types import Finding, PolicyDecision


class WarnStrategy:
    """No text transformation; emits a PolicyDecision with rationale prefixed
    ``warn:`` so observers can filter."""

    name: str = "warn"

    def apply(
        self, text: str, findings: Sequence[Finding]
    ) -> tuple[str, tuple[PolicyDecision, ...]]:
        decisions = tuple(
            PolicyDecision(
                finding_ids=(idx,),
                strategy=self.name,
                severity=f.risk_level,
                rationale=f"warn: detected {f.entity_type}",
            )
            for idx, f in enumerate(findings)
        )
        return text, decisions
