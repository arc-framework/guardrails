"""RefusalEnvelope builder."""

from __future__ import annotations

from collections.abc import Sequence

from arc_guard_core.exceptions import RefusalEnvelopeError
from arc_guard_core.policy import PolicyRule
from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.refusal.templates import get_refusal_template
from arc_guard_core.types import PolicyDecision, RefusalEnvelope


class RefusalBuilder:
    """Builds a RefusalEnvelope from a firing rule + decisions.

    Resolution order for ``human_message`` and ``next_steps``:
    1. ``firing_rule.refusal_human_message`` / ``firing_rule.refusal_next_steps`` if set.
    2. Otherwise the registered ``RefusalTemplate`` for the given ``code``.

    Result: every envelope has non-empty required fields.
    """

    def build(
        self,
        firing_rule: PolicyRule,
        decisions: Sequence[PolicyDecision],
        code: RefusalCode,
        trigger: str,
        policy_id: str,
    ) -> RefusalEnvelope:
        try:
            template = get_refusal_template(code)
        except KeyError as exc:
            raise RefusalEnvelopeError(
                f"unknown refusal code {code!r}",
                code="refusal.unknown_code",
                details={"code": str(code)},
                cause=exc,
            ) from exc

        human_message = (
            firing_rule.refusal_human_message
            if firing_rule.refusal_human_message
            else template.human_message
        )
        next_steps = (
            firing_rule.refusal_next_steps
            if firing_rule.refusal_next_steps
            else template.next_steps
        )

        if not human_message:
            raise RefusalEnvelopeError(
                "refusal envelope human_message must be non-empty",
                code="refusal.build_failed",
                details={"code": str(code), "rule_id": firing_rule.id},
            )
        if not next_steps:
            # Every envelope returned to a caller has non-empty next_steps;
            # force a safe default if both the rule and template are empty.
            next_steps = ("Adjust the request and try again.",)

        return RefusalEnvelope(
            code=str(code),
            trigger=trigger,
            policy=policy_id,
            human_message=human_message,
            decisions=tuple(decisions),
            next_steps=tuple(next_steps),
            metadata={"firing_rule_id": firing_rule.id},
        )

    def build_internal_failure(
        self,
        refusal_code: RefusalCode,
        exception_type: str,
        correlation_id: str,
        decision_id: str,
    ) -> RefusalEnvelope:
        """Build a refusal envelope for an internal pipeline failure.

        Used by the pipeline's posture-driven short-circuit path when a
        ``closed``-posture exception escapes a stage. No firing
        ``PolicyRule`` exists for these — the refusal is constructed
        directly from the registered template for the rule's
        ``refusal_code``.
        """
        try:
            template = get_refusal_template(refusal_code)
        except KeyError as exc:
            raise RefusalEnvelopeError(
                f"unknown refusal code {refusal_code!r}",
                code="refusal.unknown_code",
                details={"code": str(refusal_code)},
                cause=exc,
            ) from exc

        next_steps = template.next_steps or ("Contact support if the issue persists.",)
        return RefusalEnvelope(
            code=str(refusal_code),
            trigger=exception_type,
            policy="internal-failure",
            human_message=template.human_message,
            decisions=(),
            next_steps=tuple(next_steps),
            metadata={
                "correlation_id": correlation_id,
                "decision_id": decision_id,
                "exception_type": exception_type,
            },
        )


__all__ = ["RefusalBuilder"]
