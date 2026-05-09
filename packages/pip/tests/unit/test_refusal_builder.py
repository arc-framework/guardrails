"""RefusalBuilder unit tests."""

from __future__ import annotations

import pytest
from arc_guard_core.exceptions import RefusalEnvelopeError
from arc_guard_core.policy import PolicyRule
from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.types import PolicyDecision, RiskLevel

from arc_guard.refusal.builder import RefusalBuilder


def _decision() -> PolicyDecision:
    return PolicyDecision(
        finding_ids=(0,),
        strategy="block",
        severity=RiskLevel.CRITICAL,
        rationale="blocked by policy",
    )


def test_rule_overrides_take_precedence() -> None:
    rule = PolicyRule(
        id="r_block",
        match="INJECTION",
        strategy="block",
        refusal_human_message="Custom override message",
        refusal_next_steps=("Custom step 1", "Custom step 2"),
    )
    envelope = RefusalBuilder().build(
        firing_rule=rule,
        decisions=[_decision()],
        code=RefusalCode.JAILBREAK,
        trigger="injection",
        policy_id=rule.id,
    )
    assert envelope.human_message == "Custom override message"
    assert envelope.next_steps == ("Custom step 1", "Custom step 2")
    assert envelope.code == "jailbreak"
    assert envelope.policy == rule.id


def test_template_default_when_rule_has_no_overrides() -> None:
    rule = PolicyRule(id="r_block", match="INJECTION", strategy="block")
    envelope = RefusalBuilder().build(
        firing_rule=rule,
        decisions=[_decision()],
        code=RefusalCode.JAILBREAK,
        trigger="injection",
        policy_id=rule.id,
    )
    assert envelope.human_message  # registered template default
    assert envelope.next_steps  # registered template default
    assert "jailbreaking" in envelope.human_message.lower()


def test_empty_next_steps_falls_back_to_safe_default() -> None:
    """Every envelope returned to the user has non-empty next_steps."""
    rule = PolicyRule(
        id="r_x",
        match="X",
        strategy="block",
        refusal_human_message="msg",
        # Don't override next_steps — it's None, so template default is used.
    )
    envelope = RefusalBuilder().build(
        firing_rule=rule,
        decisions=[_decision()],
        code=RefusalCode.POLICY_BLOCK,
        trigger="t",
        policy_id="p",
    )
    assert len(envelope.next_steps) >= 1


def test_envelope_carries_firing_rule_id_in_metadata() -> None:
    rule = PolicyRule(id="r_audit", match="X", strategy="block")
    envelope = RefusalBuilder().build(
        firing_rule=rule,
        decisions=[_decision()],
        code=RefusalCode.POLICY_BLOCK,
        trigger="t",
        policy_id="p",
    )
    assert envelope.metadata["firing_rule_id"] == "r_audit"


def test_unknown_refusal_code_raises() -> None:
    rule = PolicyRule(id="r1", match="X", strategy="block")
    # Construct a fake-coded RefusalCode by bypassing validation — not realistic
    # in production but the builder must guard against it.
    with pytest.raises((RefusalEnvelopeError, ValueError, KeyError)):
        RefusalBuilder().build(
            firing_rule=rule,
            decisions=[_decision()],
            code="not_a_real_code",  # type: ignore[arg-type]
            trigger="t",
            policy_id="p",
        )
