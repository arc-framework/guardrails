"""RiskClassifier — aggregate findings into a RiskBand."""

from __future__ import annotations

from collections.abc import Sequence

from arc_guard_core.policy import PolicyRuleSet, RiskBand, RiskThresholds
from arc_guard_core.types import Finding, RiskLevel


class RiskClassifier:
    """Pure function: findings + thresholds → aggregate RiskBand.

    Aggregation: max of (per-finding ceiling, count-based escalation).
    """

    def classify(
        self,
        findings: Sequence[Finding],
        thresholds: RiskThresholds,
    ) -> tuple[RiskBand, str | None]:
        """Return (band, optional aggregation rationale marker).

        ``aggregation_marker`` is non-None when a count-based aggregation
        rule changed the band (e.g. soft-PII escalation). The router
        records the marker in the leading ``PolicyDecision.rationale`` so
        the audit trail explains why the band differs from per-finding
        severities.
        """
        if not findings:
            return RiskBand.LOW, None

        per_level: dict[RiskLevel, int] = {}
        for f in findings:
            per_level[f.risk_level] = per_level.get(f.risk_level, 0) + 1

        # Per-finding ceiling
        if per_level.get(RiskLevel.CRITICAL, 0) >= thresholds.critical_escalates_at:
            return RiskBand.CRITICAL, None
        if per_level.get(RiskLevel.HIGH, 0) >= thresholds.high_escalates_at:
            return RiskBand.HIGH, None

        medium_count = per_level.get(RiskLevel.MEDIUM, 0)
        low_count = per_level.get(RiskLevel.LOW, 0)

        # Count-based escalations
        marker: str | None = None
        if medium_count > thresholds.medium_max_count:
            return RiskBand.HIGH, f"aggregation:medium_count→HIGH ({medium_count} medium findings)"
        if low_count >= thresholds.soft_pii_aggregation:
            marker = f"aggregation:soft_pii→MEDIUM ({low_count} low findings)"
            return RiskBand.MEDIUM, marker

        # Plain band selection
        if medium_count >= 1:
            return RiskBand.MEDIUM, None
        if low_count > thresholds.low_max_count:
            return RiskBand.MEDIUM, f"aggregation:low_count→MEDIUM ({low_count} low findings)"
        return RiskBand.LOW, None


def is_ambiguous(band: RiskBand, ruleset: PolicyRuleSet) -> bool:
    """Return True when the run lands on the configured ambiguous threshold
    and clarification is enabled.
    """
    if not ruleset.clarification_enabled:
        return False
    if band == RiskBand.CRITICAL:
        return False
    return band == ruleset.ambiguous_threshold


__all__ = ["RiskClassifier", "is_ambiguous"]
