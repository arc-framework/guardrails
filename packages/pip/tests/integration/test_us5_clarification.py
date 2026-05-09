"""Clarification-mode integration: recovers ≥80% of borderline inputs."""

from __future__ import annotations

import asyncio

from arc_guard_core.policy import (
    PolicyRule,
    PolicyRuleSet,
    RiskBand,
    RiskThresholds,
)
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


def _f(et: str, start: int, end: int, risk: RiskLevel) -> Finding:
    return Finding(et, start, end, risk, "stub")


# 10 borderline inputs — each classifies as MEDIUM in the default policy.
BORDERLINE_FIXTURES: tuple[tuple[str, str, tuple[Finding, ...]], ...] = (
    ("partial_card_4_digits", "last 4 digits 4111", (_f("CREDIT_CARD", 14, 18, RiskLevel.MEDIUM),)),
    ("ambiguous_phone_reference", "the 555 number", (_f("PHONE_NUMBER", 4, 7, RiskLevel.MEDIUM),)),
    ("name_with_role", "alice the admin", (_f("CUSTOMER_NAME", 0, 5, RiskLevel.MEDIUM),)),
    ("partial_email_handle", "send to alice@", (_f("EMAIL_ADDRESS", 8, 14, RiskLevel.MEDIUM),)),
    ("project_codename", "project blue", (_f("INTERNAL_PROJECT", 8, 12, RiskLevel.MEDIUM),)),
    (
        "two_low_findings_aggregate_to_medium",
        "alice@acme.com or bob@acme.com or charlie@acme.com",
        (
            _f("EMAIL_ADDRESS", 0, 14, RiskLevel.LOW),
            _f("EMAIL_ADDRESS", 18, 30, RiskLevel.LOW),
            _f("EMAIL_ADDRESS", 34, 50, RiskLevel.LOW),
        ),
    ),
    ("location_indirect", "the SF office", (_f("CONFIDENTIAL_LOCATION", 4, 6, RiskLevel.MEDIUM),)),
    ("ip_partial", "192.168.1.x", (_f("IP_ADDRESS", 0, 11, RiskLevel.MEDIUM),)),
    ("name_in_quote", '"Bob said it"', (_f("CUSTOMER_NAME", 1, 4, RiskLevel.MEDIUM),)),
    ("email_with_alias", "alice+test@acme.com", (_f("EMAIL_ADDRESS", 0, 19, RiskLevel.MEDIUM),)),
)


def _build_pipeline(findings: tuple[Finding, ...]) -> GuardPipeline:
    policy = PolicyRuleSet(
        rules=(
            PolicyRule(id="r_card", match="CREDIT_CARD", strategy="redact"),
            PolicyRule(id="r_phone", match="PHONE_NUMBER", strategy="redact"),
            PolicyRule(id="r_name", match="CUSTOMER_NAME", strategy="redact"),
            PolicyRule(id="r_email", match="EMAIL_ADDRESS", strategy="redact"),
            PolicyRule(id="r_proj", match="INTERNAL_PROJECT", strategy="redact"),
            PolicyRule(id="r_loc", match="CONFIDENTIAL_LOCATION", strategy="redact"),
            PolicyRule(id="r_ip", match="IP_ADDRESS", strategy="redact"),
        ),
        risk_thresholds=RiskThresholds(),
        clarification_enabled=True,
        ambiguous_threshold=RiskBand.MEDIUM,
    )
    return GuardPipeline(
        policy_ruleset=policy,
        inspectors=[_StubInspector(findings)],
    )


def test_walkthrough_b5_single_borderline_returns_clarification() -> None:
    """B.5 — a partial card number is ambiguous → clarification populated."""
    case = BORDERLINE_FIXTURES[0]
    _, text, findings = case
    pipeline = _build_pipeline(findings)
    result = asyncio.run(pipeline.pre_process(GuardInput(text=text)))
    assert result.clarification is not None
    assert result.clarification.suggested_rephrase
    assert len(result.clarification.next_steps) >= 1
    assert result.clarification.triggering_rule_id is not None


def test_clarification_recovery_rate_at_least_80_percent() -> None:
    """At least 80% of the 10-input borderline suite returns clarification."""
    recovered = 0
    for case_id, text, findings in BORDERLINE_FIXTURES:
        pipeline = _build_pipeline(findings)
        result = asyncio.run(pipeline.pre_process(GuardInput(text=text)))
        if result.clarification is not None:
            recovered += 1
    rate = recovered / len(BORDERLINE_FIXTURES)
    assert rate >= 0.8, (
        f"clarification recovery rate {rate:.0%} < 80% "
        f"({recovered}/{len(BORDERLINE_FIXTURES)} inputs)"
    )
