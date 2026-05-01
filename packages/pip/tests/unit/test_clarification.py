"""Clarification flow unit tests."""

from __future__ import annotations

import asyncio

import pytest
from arc_guard_core.policy import (
    PolicyRule,
    PolicyRuleSet,
    RiskBand,
    RiskThresholds,
)
from arc_guard_core.types import Finding, GuardInput, GuardResult, RiskLevel

from arc_guard.pipeline import GuardPipeline
from arc_guard.policy.classifier import is_ambiguous


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


def test_is_ambiguous_disabled_returns_false() -> None:
    rs = PolicyRuleSet(
        rules=(PolicyRule(id="r1", match="X", strategy="redact"),),
        clarification_enabled=False,
    )
    assert is_ambiguous(RiskBand.MEDIUM, rs) is False


def test_is_ambiguous_critical_never_ambiguous() -> None:
    rs = PolicyRuleSet(
        rules=(PolicyRule(id="r1", match="X", strategy="redact"),),
        clarification_enabled=True,
        ambiguous_threshold=RiskBand.MEDIUM,
    )
    assert is_ambiguous(RiskBand.CRITICAL, rs) is False


def test_is_ambiguous_at_threshold_returns_true() -> None:
    rs = PolicyRuleSet(
        rules=(PolicyRule(id="r1", match="X", strategy="redact"),),
        clarification_enabled=True,
        ambiguous_threshold=RiskBand.MEDIUM,
    )
    assert is_ambiguous(RiskBand.MEDIUM, rs) is True
    assert is_ambiguous(RiskBand.HIGH, rs) is False


def test_clarification_populated_when_enabled_and_ambiguous() -> None:
    policy = PolicyRuleSet(
        rules=(PolicyRule(id="r_card", match="CREDIT_CARD", strategy="redact"),),
        risk_thresholds=RiskThresholds(),
        clarification_enabled=True,
        ambiguous_threshold=RiskBand.MEDIUM,
    )
    findings = (Finding("CREDIT_CARD", 0, 16, RiskLevel.MEDIUM, "stub"),)
    pipeline = GuardPipeline(
        policy_ruleset=policy,
        inspectors=[_StubInspector(findings)],
    )
    result = asyncio.run(pipeline.pre_process(GuardInput(text="4111111111111111")))
    assert result.clarification is not None
    assert result.refusal is None
    assert result.action == "pass"
    assert result.clarification.suggested_rephrase
    assert len(result.clarification.next_steps) >= 1


def test_clarification_disabled_falls_back_to_block_or_redact() -> None:
    policy = PolicyRuleSet(
        rules=(PolicyRule(id="r_card", match="CREDIT_CARD", strategy="redact"),),
        clarification_enabled=False,
    )
    findings = (Finding("CREDIT_CARD", 0, 16, RiskLevel.MEDIUM, "stub"),)
    pipeline = GuardPipeline(
        policy_ruleset=policy,
        inspectors=[_StubInspector(findings)],
    )
    result = asyncio.run(pipeline.pre_process(GuardInput(text="4111111111111111")))
    assert result.clarification is None


def test_clarification_block_invariant_enforced() -> None:
    """Clarification populated implies action != 'block'."""
    from arc_guard_core.types import ClarificationRequest, RefusalEnvelope

    cr = ClarificationRequest(suggested_rephrase="ok")
    refusal = RefusalEnvelope(
        code="policy_block",
        trigger="t",
        policy="p",
        human_message="msg",
    )
    with pytest.raises(ValueError):
        GuardResult(text="", action="block", refusal=refusal, clarification=cr)
