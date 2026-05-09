"""RiskClassifier 16-row matrix (4 bands × 4 entity mixes) plus the aggregation-marker assertion."""

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
from arc_guard.policy.classifier import RiskClassifier


def _f(et: str, risk: RiskLevel) -> Finding:
    return Finding(et, 0, 1, risk, "stub")


_THRESHOLDS = RiskThresholds()
_CLF = RiskClassifier()


# 4 bands × 4 entity mixes = 16 rows.
MATRIX = [
    # LOW band
    ("low_single", [_f("EMAIL_ADDRESS", RiskLevel.LOW)], RiskBand.LOW),
    (
        "low_two",
        [_f("EMAIL_ADDRESS", RiskLevel.LOW), _f("PHONE_NUMBER", RiskLevel.LOW)],
        RiskBand.LOW,
    ),
    ("low_empty", [], RiskBand.LOW),
    (
        "low_only_low_findings_under_aggregation_threshold",
        [_f("EMAIL_ADDRESS", RiskLevel.LOW), _f("PHONE_NUMBER", RiskLevel.LOW)],
        RiskBand.LOW,
    ),
    # MEDIUM band
    ("medium_single", [_f("CREDIT_CARD", RiskLevel.MEDIUM)], RiskBand.MEDIUM),
    (
        "medium_two",
        [_f("CREDIT_CARD", RiskLevel.MEDIUM), _f("PHONE_NUMBER", RiskLevel.MEDIUM)],
        RiskBand.MEDIUM,
    ),
    ("medium_via_soft_pii_aggregation", [_f("EMAIL_ADDRESS", RiskLevel.LOW)] * 3, RiskBand.MEDIUM),
    (
        "medium_via_low_count_overflow",
        [_f("EMAIL_ADDRESS", RiskLevel.LOW)] * 4,
        RiskBand.MEDIUM,
    ),  # >= soft_pii_aggregation triggers
    # HIGH band
    ("high_single", [_f("US_SSN", RiskLevel.HIGH)], RiskBand.HIGH),
    (
        "high_with_low",
        [_f("US_SSN", RiskLevel.HIGH), _f("EMAIL_ADDRESS", RiskLevel.LOW)],
        RiskBand.HIGH,
    ),
    ("high_via_medium_count_overflow", [_f("CREDIT_CARD", RiskLevel.MEDIUM)] * 5, RiskBand.HIGH),
    (
        "high_two_high_findings",
        [_f("US_SSN", RiskLevel.HIGH), _f("US_SSN", RiskLevel.HIGH)],
        RiskBand.HIGH,
    ),
    # CRITICAL band
    ("critical_single", [_f("INJECTION", RiskLevel.CRITICAL)], RiskBand.CRITICAL),
    (
        "critical_with_low",
        [_f("INJECTION", RiskLevel.CRITICAL), _f("EMAIL_ADDRESS", RiskLevel.LOW)],
        RiskBand.CRITICAL,
    ),
    (
        "critical_with_high",
        [_f("INJECTION", RiskLevel.CRITICAL), _f("US_SSN", RiskLevel.HIGH)],
        RiskBand.CRITICAL,
    ),
    ("critical_two_critical", [_f("INJECTION", RiskLevel.CRITICAL)] * 2, RiskBand.CRITICAL),
]


@pytest.mark.parametrize(
    ("case_id", "findings", "expected_band"),
    MATRIX,
    ids=[row[0] for row in MATRIX],
)
def test_classification_matrix(
    case_id: str, findings: list[Finding], expected_band: RiskBand
) -> None:
    band, _marker = _CLF.classify(findings, _THRESHOLDS)
    assert band == expected_band, f"{case_id}: expected {expected_band}, got {band}"


def test_soft_pii_aggregation_reports_marker() -> None:
    findings = [_f("EMAIL_ADDRESS", RiskLevel.LOW)] * 3
    band, marker = _CLF.classify(findings, _THRESHOLDS)
    assert band == RiskBand.MEDIUM
    assert marker is not None
    assert "aggregation:soft_pii→MEDIUM" in marker


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


def test_aggregation_marker_recorded_in_decision_rationale() -> None:
    """The aggregation marker MUST appear in the rationale when it changes the band."""
    policy = PolicyRuleSet(
        rules=(PolicyRule(id="r_email", match="EMAIL_ADDRESS", strategy="redact"),),
    )
    findings = tuple(_f("EMAIL_ADDRESS", RiskLevel.LOW) for _ in range(3))
    # Findings need distinct spans for the redact strategy to operate.
    findings = tuple(
        Finding("EMAIL_ADDRESS", i * 5, i * 5 + 4, RiskLevel.LOW, "stub") for i in range(3)
    )
    pipeline = GuardPipeline(
        policy_ruleset=policy,
        inspectors=[_StubInspector(findings)],
    )
    result = asyncio.run(pipeline.pre_process(GuardInput(text="aaaaaaaaaaaaaaaaa")))
    assert any("aggregation:soft_pii" in d.rationale for d in result.decisions), (
        "leading PolicyDecision rationale must record the aggregation marker"
    )
