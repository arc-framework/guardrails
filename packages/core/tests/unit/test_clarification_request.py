"""T025 — ClarificationRequest tests + GuardResult.clarification invariant."""

from __future__ import annotations

import pytest

from arc_guard_core.types import ClarificationRequest, GuardResult, RefusalEnvelope


def test_clarification_request_construction() -> None:
    cr = ClarificationRequest(
        suggested_rephrase="Try without the SSN",
        next_steps=("Remove the digits",),
        triggering_rule_id="r1",
    )
    assert cr.suggested_rephrase == "Try without the SSN"
    assert cr.next_steps == ("Remove the digits",)
    assert cr.triggering_rule_id == "r1"
    assert cr.metadata == {}


def test_clarification_request_empty_rephrase_rejected() -> None:
    with pytest.raises(ValueError):
        ClarificationRequest(suggested_rephrase="")


def test_guard_result_clarification_field_default_none() -> None:
    result = GuardResult(text="hi")
    assert result.clarification is None


def test_guard_result_clarification_with_block_rejected() -> None:
    cr = ClarificationRequest(suggested_rephrase="ok")
    refusal = RefusalEnvelope(
        code="policy_block",
        trigger="x",
        policy="p",
        human_message="blocked",
    )
    with pytest.raises(ValueError):
        GuardResult(
            text="",
            action="block",
            refusal=refusal,
            clarification=cr,
        )


def test_guard_result_clarification_with_pass_allowed() -> None:
    cr = ClarificationRequest(suggested_rephrase="ok")
    result = GuardResult(text="hi", action="pass", clarification=cr)
    assert result.clarification is cr
