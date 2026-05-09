"""Jailbreak threshold ladder dispatches the four bands correctly.

Direction: INVERSE relative to FidelityThresholds. Higher confidence
means more risk; the ordering is ``refuse > clarify > warn``.
"""

from __future__ import annotations

import pytest
from arc_guard_core.jailbreak import JailbreakSignal
from arc_guard_core.observability_config import JailbreakThresholds
from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.types import GuardResult

from arc_guard.jailbreak.ladder import apply_jailbreak_ladder

THRESHOLDS = JailbreakThresholds(refuse=0.8, clarify=0.6, warn=0.4)


def _signal(confidence: float) -> JailbreakSignal:
    return JailbreakSignal(
        category="direct_override",
        confidence=confidence,
        evidence_reference="STUB",
        detector_id="stub:1",
    )


@pytest.mark.parametrize(
    ("confidence", "band"),
    [
        (0.95, "refuse"),
        (0.7, "clarify"),
        (0.5, "warn"),
        (0.2, "no_action"),
    ],
)
def test_each_band_produces_documented_result_shape(
    confidence: float,
    band: str,
) -> None:
    result = GuardResult(text="answer", action="pass")
    out = apply_jailbreak_ladder(result, [_signal(confidence)], THRESHOLDS)

    if band == "refuse":
        assert out.action == "block"
        assert out.refusal is not None
        assert out.refusal.code == str(RefusalCode.JAILBREAK_STRONG)
        assert out.clarification is None
    elif band == "clarify":
        assert out.action != "block"
        assert out.clarification is not None
        assert out.clarification.suggested_rephrase
        assert out.refusal is None
    elif band == "warn":
        # Warn band — no action change at the ladder level (the
        # warn-class indicator is recorded on the decision record by
        # the pipeline, not by the ladder helper).
        assert out.action == result.action
        assert out.clarification is None
        assert out.refusal is None
    else:  # no_action
        assert out.action == result.action
        assert out.clarification is None
        assert out.refusal is None


def test_existing_block_action_is_not_demoted() -> None:
    """Risk-precedence: an existing block stays a block even on low confidence."""
    from arc_guard_core.types import RefusalEnvelope

    risk_refusal = RefusalEnvelope(
        code="policy_block",
        trigger="policy",
        policy="policy.example",
        human_message="blocked by policy",
    )
    result = GuardResult(
        text="",
        action="block",
        refusal=risk_refusal,
    )
    out = apply_jailbreak_ladder(result, [_signal(0.99)], THRESHOLDS)
    # Same action and same refusal — jailbreak ladder did not overwrite.
    assert out.action == "block"
    assert out.refusal is risk_refusal
    assert out.refusal.code == "policy_block"


def test_no_signals_is_no_op() -> None:
    result = GuardResult(text="answer", action="pass")
    out = apply_jailbreak_ladder(result, [], THRESHOLDS)
    assert out is result or (
        out.action == "pass" and out.clarification is None and out.refusal is None
    )


def test_highest_confidence_signal_dispatches() -> None:
    """When multiple signals are present, the top-confidence one drives the band."""
    result = GuardResult(text="answer", action="pass")
    signals = [_signal(0.3), _signal(0.95), _signal(0.5)]
    out = apply_jailbreak_ladder(result, signals, THRESHOLDS)
    # 0.95 lands in refuse band → block.
    assert out.action == "block"
    assert out.refusal is not None
