"""Threshold-driven action ladder for jailbreak signals.

``apply_jailbreak_ladder(result, signals, thresholds)`` returns a new
``GuardResult`` per the documented INVERSE-direction band mapping
(higher confidence = more risk):

- ``confidence >= thresholds.refuse`` → populate ``GuardResult.refusal``
  with ``RefusalCode.JAILBREAK_STRONG`` and set ``action="block"``.
- ``thresholds.clarify <= confidence < thresholds.refuse`` → populate
  ``GuardResult.clarification`` with a jailbreak-driven rephrase.
- ``thresholds.warn <= confidence < thresholds.clarify`` → no action
  change; informational warn-class indicator (recorded on the
  decision record by the pipeline).
- ``confidence < thresholds.warn`` → no change.

When multiple signals are present, the helper uses the
highest-confidence signal for the dispatch decision.

Risk-precedence rule: when ``result.action == "block"`` already or
``result.refusal is not None``, the ladder is a no-op.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

from arc_guard_core.jailbreak import JailbreakSignal
from arc_guard_core.observability_config import JailbreakThresholds
from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.refusal.templates import get_refusal_template
from arc_guard_core.types import (
    ClarificationRequest,
    GuardResult,
    RefusalEnvelope,
)

_JAILBREAK_TRIGGER = "jailbreak_strong"
_JAILBREAK_POLICY = "jailbreak_threshold_ladder"
_JAILBREAK_CLARIFICATION_REPHRASE = (
    "Rephrase the question directly without role-play, hypothetical, or override-style framing."
)


def apply_jailbreak_ladder(
    result: GuardResult,
    signals: Sequence[JailbreakSignal],
    thresholds: JailbreakThresholds,
) -> GuardResult:
    """Dispatch the jailbreak action ladder against ``result``.

    Returns a new ``GuardResult`` (preserves ``frozen=True`` via
    ``dataclasses.replace``). Returns ``result`` unchanged when no
    signals are present, all signals are below ``warn``, or
    risk-precedence is enforced.
    """
    if not signals:
        return result
    if result.action == "block" or result.refusal is not None:
        return result

    top = max(signals, key=lambda s: s.confidence)
    confidence = top.confidence

    if confidence >= thresholds.refuse:
        template = get_refusal_template(RefusalCode.JAILBREAK_STRONG)
        refusal = RefusalEnvelope(
            code=str(RefusalCode.JAILBREAK_STRONG),
            trigger=_JAILBREAK_TRIGGER,
            policy=_JAILBREAK_POLICY,
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

    if confidence >= thresholds.clarify:
        if result.clarification is not None:
            return result
        clarification = ClarificationRequest(
            suggested_rephrase=_JAILBREAK_CLARIFICATION_REPHRASE,
            next_steps=(
                "Avoid 'imagine if' / 'hypothetically' / 'you are now' framings.",
                "State the actual question directly.",
            ),
            triggering_rule_id=None,
        )
        return dataclasses.replace(result, clarification=clarification)

    # warn band or below — no action change.
    return result


__all__ = ["apply_jailbreak_ladder"]
