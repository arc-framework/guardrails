"""ClarificationRequest builder (Spec 003 FR-018–FR-020, D1)."""

from __future__ import annotations

from collections.abc import Sequence

from arc_guard_core.policy import PolicyRule
from arc_guard_core.types import ClarificationRequest, Finding


def build_clarification(
    firing_rule: PolicyRule | None,
    findings: Sequence[Finding],
) -> ClarificationRequest:
    """Build a ClarificationRequest for an ambiguous run.

    The suggested rephrase is drawn from the firing rule's
    ``rationale_template`` if non-empty; otherwise from a generic
    fallback derived from the dominant finding entity type.
    """
    if firing_rule is not None and firing_rule.rationale_template:
        rephrase = firing_rule.rationale_template
    elif findings:
        types = {f.entity_type for f in findings}
        joined = ", ".join(sorted(types))
        rephrase = (
            f"This request was flagged as ambiguous (detected: {joined}). "
            "Please rephrase removing or generalizing the sensitive details."
        )
    else:
        rephrase = "Please rephrase the request more specifically."

    next_steps: tuple[str, ...] = (
        "Re-submit a rephrased version that omits the flagged details.",
    )

    return ClarificationRequest(
        suggested_rephrase=rephrase,
        next_steps=next_steps,
        triggering_rule_id=firing_rule.id if firing_rule else None,
    )


__all__ = ["build_clarification"]
