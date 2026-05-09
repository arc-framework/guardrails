"""Conditional event: PolicyRuleEvaluated fires once per rule in the ruleset."""

from __future__ import annotations

import asyncio

import pytest
from arc_guard_core.lifecycle import LifecycleEmitter
from arc_guard_core.lifecycle.events import PolicyRuleEvaluated
from arc_guard_core.policy import PolicyRule, PolicyRuleSet
from arc_guard_core.types import Finding, GuardContext, GuardInput, GuardResult, RiskLevel

from arc_guard.observability.ring_buffer_lifecycle_sink import RingBufferLifecycleSink
from arc_guard.pipeline import GuardPipeline


class _StubInspector:
    name = "stub"

    def __init__(self, findings: tuple[Finding, ...]) -> None:
        self._findings = findings

    async def inspect(self, result: GuardResult) -> GuardResult:
        return GuardResult(
            text=result.text,
            action=result.action,
            findings=tuple(result.findings) + self._findings,
            phase=result.phase,
        )


@pytest.mark.asyncio
async def test_three_rules_emit_three_policy_rule_evaluated_events() -> None:
    sink = RingBufferLifecycleSink(capacity=200)
    rid = "rule-eval-three"
    emitter = LifecycleEmitter(sink, rid)

    policy = PolicyRuleSet(
        rules=(
            PolicyRule(id="r_email", match="EMAIL_ADDRESS", strategy="redact"),
            PolicyRule(id="r_phone", match="PHONE_NUMBER", strategy="redact"),
            PolicyRule(id="r_card", match="CREDIT_CARD", strategy="redact"),
        ),
    )
    inspector = _StubInspector(
        findings=(Finding("EMAIL_ADDRESS", 0, 5, RiskLevel.MEDIUM, "stub"),),
    )
    pipeline = GuardPipeline(
        policy_ruleset=policy,
        inspectors=[inspector],
        lifecycle_hook=sink,
    )

    await pipeline.pre_process(
        GuardInput(
            text="hello world",
            context=GuardContext(
                metadata={"_lifecycle_emitter": emitter, "_lifecycle_parent_id": None},
            ),
        )
    )
    await asyncio.sleep(0.05)

    events = await sink.query(rid)
    assert events is not None
    rule_events = [e for e in events if isinstance(e, PolicyRuleEvaluated)]
    assert len(rule_events) == 3, f"expected 3 PolicyRuleEvaluated, got {len(rule_events)}"
    rule_ids = {e.rule_id for e in rule_events}
    assert rule_ids == {"r_email", "r_phone", "r_card"}

    by_id = {e.rule_id: e for e in rule_events}
    assert by_id["r_email"].outcome == "matched"
    assert by_id["r_email"].contributed_to_action is True
    assert by_id["r_phone"].outcome == "not_applicable"
    assert by_id["r_phone"].contributed_to_action is False
    assert by_id["r_card"].outcome == "not_applicable"
    assert by_id["r_card"].contributed_to_action is False
