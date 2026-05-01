"""BlockStrategy — empties the text and signals a block decision."""

from __future__ import annotations

from collections.abc import Sequence

from arc_guard_core.types import Finding, PolicyDecision, RiskLevel


class BlockStrategy:
    """Returns empty text. The router builds the RefusalEnvelope."""

    name: str = "block"

    def apply(
        self, text: str, findings: Sequence[Finding]
    ) -> tuple[str, tuple[PolicyDecision, ...]]:
        if not findings:
            return "", (
                PolicyDecision(
                    finding_ids=(),
                    strategy=self.name,
                    severity=RiskLevel.CRITICAL,
                    rationale="blocked by policy (no findings)",
                ),
            )
        decisions = tuple(
            PolicyDecision(
                finding_ids=(idx,),
                strategy=self.name,
                severity=f.risk_level,
                rationale=f"blocked: {f.entity_type}",
            )
            for idx, f in enumerate(findings)
        )
        return "", decisions
