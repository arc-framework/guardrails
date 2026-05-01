"""RefusalEnvelope builder (Spec 003 FR-014–FR-017)."""

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

    Result: every envelope has non-empty required fields (FR-014, FR-016).
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
            # FR-016: every envelope returned to the user has non-empty next_steps.
            # Force the registered default if both rule and template are empty.
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


__all__ = ["RefusalBuilder"]
