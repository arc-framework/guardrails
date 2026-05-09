"""Threshold-driven action ladder for the deception score.

INVERSE direction relative to ``FidelityThresholds``: higher score =
more deception (worse). The ladder dispatches:

- ``score.value >= refuse`` → populate ``GuardResult.refusal`` with
  ``RefusalCode.DECEPTION_DRIFT`` and set ``action="block"``.
- ``clarify <= score.value < refuse`` → populate
  ``GuardResult.clarification`` with a deception-driven rephrase.
- ``warn <= score.value < clarify`` → no action change (informational
  warn-class indicator recorded on the decision record by the pipeline).
- ``score.value < warn`` → no change.

Sentinel handling: when ``score.sentinel == "not_measured"``, the
ladder is a no-op.

Risk-precedence: when ``result.action == "block"`` already or
``result.refusal is not None``, the ladder is a no-op.
"""

from __future__ import annotations

import dataclasses

from arc_guard_core.deception import DeceptionScore
from arc_guard_core.observability_config import DeceptionThresholds
from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.refusal.templates import get_refusal_template
from arc_guard_core.types import (
    ClarificationRequest,
    GuardResult,
    RefusalEnvelope,
)

_DECEPTION_TRIGGER = "deception_drift"
_DECEPTION_POLICY = "deception_threshold_ladder"
_DECEPTION_CLARIFICATION_REPHRASE = (
    "Start a fresh conversation and rephrase your original intent directly, "
    "without referencing past role-play or 'as we already agreed' framings."
)


def apply_deception_ladder(
    result: GuardResult,
    score: DeceptionScore,
    thresholds: DeceptionThresholds,
) -> GuardResult:
    """Dispatch the deception action ladder against ``result``.

    Returns a new ``GuardResult`` (preserves ``frozen=True`` via
    ``dataclasses.replace``). Returns ``result`` unchanged when the
    ladder is a no-op (sentinel, below-warn, or risk precedence).
    """
    if score.sentinel != "measured" or score.value is None:
        return result
    if result.action == "block" or result.refusal is not None:
        return result

    value = score.value

    if value >= thresholds.refuse:
        template = get_refusal_template(RefusalCode.DECEPTION_DRIFT)
        refusal = RefusalEnvelope(
            code=str(RefusalCode.DECEPTION_DRIFT),
            trigger=_DECEPTION_TRIGGER,
            policy=_DECEPTION_POLICY,
            human_message=template.human_message,
            next_steps=template.next_steps,
        )
        return dataclasses.replace(
            result,
            action="block",
            text="",
            refusal=refusal,
            clarification=None,
        )

    if value >= thresholds.clarify:
        if result.clarification is not None:
            return result
        clarification = ClarificationRequest(
            suggested_rephrase=_DECEPTION_CLARIFICATION_REPHRASE,
            next_steps=(
                "Avoid 'as we agreed' / 'we already discussed' framings.",
                "Restate the original question without the conversation history.",
            ),
            triggering_rule_id=None,
        )
        return dataclasses.replace(result, clarification=clarification)

    # warn band or below — no action change.
    return result


__all__ = ["apply_deception_ladder"]
