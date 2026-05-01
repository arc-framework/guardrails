"""US6 integration: every pipeline run produces a complete DecisionRecord."""

from __future__ import annotations

import asyncio

from arc_guard_core.policy import PolicyRule, PolicyRuleSet
from arc_guard_core.types import Finding, GuardInput, GuardResult, RiskLevel

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


def _f(et: str, start: int, end: int, risk: RiskLevel = RiskLevel.MEDIUM) -> Finding:
    return Finding(et, start, end, risk, "stub")


def test_decision_record_built_for_every_run() -> None:
    policy = PolicyRuleSet(
        rules=(
            PolicyRule(id="r_email", match="EMAIL_ADDRESS", strategy="redact"),
            PolicyRule(id="r_card", match="CREDIT_CARD", strategy="hash"),
        ),
    )
    findings = (
        _f("EMAIL_ADDRESS", 6, 20, RiskLevel.LOW),
        _f("CREDIT_CARD", 26, 42, RiskLevel.MEDIUM),
    )
    pipeline = GuardPipeline(
        policy_ruleset=policy,
        inspectors=[_StubInspector(findings)],
    )
    asyncio.run(pipeline.pre_process(GuardInput(text="Email alice@acme.com card 4111111111111111")))

    record = pipeline._last_decision
    assert record is not None
    assert len(record.findings) == 2
    assert {f.entity_type for f in record.findings} == {"EMAIL_ADDRESS", "CREDIT_CARD"}
    # Spans only — length is recorded.
    for f in record.findings:
        assert f.length == f.end - f.start
    # Transforms align with applied strategies.
    assert len(record.transforms) >= 1
    # Fired-rule ids match the rule definitions.
    assert set(record.fired_rules) <= {"r_email", "r_card"}
    # Latency is finite and non-negative.
    assert record.latency_ms >= 0.0


def test_decision_record_aggregate_band_propagated() -> None:
    policy = PolicyRuleSet(
        rules=(PolicyRule(id="r_ssn", match="US_SSN", strategy="redact"),),
    )
    findings = (_f("US_SSN", 0, 11, RiskLevel.HIGH),)
    pipeline = GuardPipeline(
        policy_ruleset=policy,
        inspectors=[_StubInspector(findings)],
    )
    asyncio.run(pipeline.pre_process(GuardInput(text="123-45-6789")))
    record = pipeline._last_decision
    assert record is not None
    assert record.aggregate_band.value == "high"


def test_decision_record_skipped_when_policy_is_none() -> None:
    """Legacy fallback path — no policy means no DecisionRecord is built."""
    pipeline = GuardPipeline(inspectors=[_StubInspector(())])
    asyncio.run(pipeline.pre_process(GuardInput(text="hi")))
    # With no policy, the emitter is never called.
    assert pipeline._last_decision is None
