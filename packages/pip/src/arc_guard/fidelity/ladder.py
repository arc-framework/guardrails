"""Threshold-driven action ladder for the fidelity score.

``apply_fidelity_ladder(result, score, thresholds)`` returns a new
``GuardResult`` with the appropriate fidelity-driven field populated:

- ``score >= thresholds.warn`` (above_warn band) → no change.
- ``thresholds.clarify <= score < thresholds.warn`` (warn band) →
  ``fidelity_warning = True``; action unchanged.
- ``thresholds.refuse <= score < thresholds.clarify`` (clarify band) →
  ``clarification`` populated with a fidelity-driven suggested rephrase.
- ``score < thresholds.refuse`` (refuse band) → ``refusal`` populated
  with ``RefusalCode.FIDELITY_DROP`` and ``action="block"``.

Risk-precedence rule: when ``result.action == "block"`` already or
``result.refusal is not None``, the ladder is a no-op. Risk takes
precedence over fidelity for safety-critical decisions; the fidelity
ladder is an additive signal that can promote, never demote.

When ``score.sentinel != "measured"``, the ladder is a no-op — the
sentinel is informational and does not trigger any action.
"""

from __future__ import annotations

import dataclasses

from arc_guard_core.fidelity import FidelityScore
from arc_guard_core.observability_config import FidelityThresholds
from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.refusal.templates import get_refusal_template
from arc_guard_core.types import (
    ClarificationRequest,
    GuardResult,
    RefusalEnvelope,
)


_FIDELITY_CLARIFICATION_REPHRASE = (
    "Rephrase the question more directly so the model can address it cleanly."
)
_FIDELITY_TRIGGER = "fidelity_drop"
_FIDELITY_POLICY = "fidelity_threshold_ladder"


def apply_fidelity_ladder(
    result: GuardResult,
    score: FidelityScore,
    thresholds: FidelityThresholds,
) -> GuardResult:
    """Dispatch the fidelity action ladder against ``result``.

    Returns a new ``GuardResult`` (preserves the ``frozen=True``
    invariant via ``dataclasses.replace``). Returns ``result`` unchanged
    when the ladder is a no-op (sentinel score, above_warn band, or
    risk precedence enforced).
    """
    if score.sentinel != "measured" or score.value is None:
        return result
    # Risk precedence: a risk-band refusal already populated cannot be
    # downgraded by the fidelity ladder.
    if result.action == "block" or result.refusal is not None:
        return result

    value = score.value
    if value >= thresholds.warn:
        # above_warn — informational only.
        return result

    if value >= thresholds.clarify:
        # warn band — set the typed boolean indicator.
        return dataclasses.replace(result, fidelity_warning=True)

    if value >= thresholds.refuse:
        # clarify band — populate ClarificationRequest.
        # Mutual exclusivity with action="block" is enforced by
        # GuardResult.__post_init__; we never set both.
        if result.clarification is not None:
            # Existing clarification (e.g. from policy) takes precedence;
            # don't overwrite. Still set fidelity_warning=False.
            return result
        clarification = ClarificationRequest(
            suggested_rephrase=_FIDELITY_CLARIFICATION_REPHRASE,
            next_steps=(
                "Simplify the request.",
                "Split a multi-part question into separate prompts.",
            ),
            triggering_rule_id=None,
        )
        return dataclasses.replace(result, clarification=clarification)

    # refuse band — populate RefusalEnvelope and block.
    template = get_refusal_template(RefusalCode.FIDELITY_DROP)
    refusal = RefusalEnvelope(
        code=str(RefusalCode.FIDELITY_DROP),
        trigger=_FIDELITY_TRIGGER,
        policy=_FIDELITY_POLICY,
        human_message=template.human_message,
        next_steps=template.next_steps,
    )
    # Setting action="block" requires clarification be None — ensure it.
    return dataclasses.replace(
        result,
        action="block",
        text="",
        refusal=refusal,
        clarification=None,
    )


__all__ = ["apply_fidelity_ladder"]
