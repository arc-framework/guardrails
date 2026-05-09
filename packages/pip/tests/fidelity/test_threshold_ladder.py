"""Threshold ladder dispatches the four bands correctly."""

from __future__ import annotations

import pytest
from arc_guard_core.fidelity import NOT_MEASURED, FidelityScore
from arc_guard_core.observability_config import FidelityThresholds
from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.types import GuardResult

from arc_guard.fidelity.ladder import apply_fidelity_ladder

THRESHOLDS = FidelityThresholds(warn=0.7, clarify=0.5, refuse=0.3)


@pytest.mark.parametrize(
    ("value", "band"),
    [
        (0.9, "above_warn"),
        (0.6, "warn"),
        (0.4, "clarify"),
        (0.1, "refuse"),
    ],
)
def test_each_band_produces_documented_result_shape(value: float, band: str) -> None:
    result = GuardResult(text="answer", action="pass")
    score = FidelityScore.measured(value)
    out = apply_fidelity_ladder(result, score, THRESHOLDS)

    if band == "above_warn":
        assert out.fidelity_warning is False
        assert out.clarification is None
        assert out.refusal is None
        assert out.action == "pass"
    elif band == "warn":
        assert out.fidelity_warning is True
        assert out.clarification is None
        assert out.refusal is None
        assert out.action == "pass"
    elif band == "clarify":
        assert out.fidelity_warning is False
        assert out.clarification is not None
        assert out.clarification.suggested_rephrase
        assert out.refusal is None
        assert out.action != "block"
    elif band == "refuse":
        assert out.fidelity_warning is False
        assert out.clarification is None
        assert out.refusal is not None
        assert out.refusal.code == str(RefusalCode.FIDELITY_DROP)
        assert out.action == "block"
    else:  # pragma: no cover
        raise AssertionError(f"unknown band {band}")


def test_sentinel_score_is_no_op() -> None:
    result = GuardResult(text="answer", action="pass")
    out = apply_fidelity_ladder(result, NOT_MEASURED, THRESHOLDS)
    assert out is result or (
        out.fidelity_warning is False
        and out.clarification is None
        and out.refusal is None
    )


def test_existing_block_action_is_not_demoted() -> None:
    """Risk-precedence: a risk-band block stays a block even on low fidelity."""
    from arc_guard_core.types import RefusalEnvelope

    risk_refusal = RefusalEnvelope(
        code="jailbreak",
        trigger="jailbreak",
        policy="policy.jailbreak",
        human_message="blocked by policy",
    )
    result = GuardResult(
        text="",
        action="block",
        refusal=risk_refusal,
    )
    out = apply_fidelity_ladder(result, FidelityScore.measured(0.1), THRESHOLDS)
    # Same action and same refusal — fidelity ladder did not overwrite.
    assert out.action == "block"
    assert out.refusal is risk_refusal
    assert out.refusal.code == "jailbreak"
