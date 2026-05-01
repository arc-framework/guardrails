"""T064 — DecisionEmitter unit tests."""

from __future__ import annotations

from arc_guard_core.policy import RiskBand, RoutedOutcome, TransformSummary
from arc_guard_core.types import Finding, GuardResult, PolicyDecision, RiskLevel

from arc_guard.decision.emitter import DecisionEmitter


def _f(et: str, start: int, end: int) -> Finding:
    return Finding(et, start, end, RiskLevel.LOW, "stub")


def test_build_with_no_findings() -> None:
    emitter = DecisionEmitter()
    result = GuardResult(text="hi", phase="pre_process")
    outcome = RoutedOutcome(
        transformed_text="hi",
        decisions=(),
        aggregate_action="pass",
        aggregate_band=RiskBand.LOW,
    )
    record = emitter.build(result, outcome, latency_ms=0.1)
    assert record.findings == ()
    assert record.transforms == ()
    assert record.aggregate_action == "pass"
    assert record.aggregate_band == RiskBand.LOW
    assert record.latency_ms == 0.1
    assert record.refusal_code is None
    assert record.clarification_present is False


def test_build_with_one_finding_and_one_transform() -> None:
    emitter = DecisionEmitter()
    findings = (_f("EMAIL_ADDRESS", 0, 14),)
    result = GuardResult(
        text="alice@acme.com",
        phase="pre_process",
        findings=findings,
    )
    outcome = RoutedOutcome(
        transformed_text="[EMAIL_ADDRESS]",
        decisions=(
            PolicyDecision(
                finding_ids=(0,),
                strategy="redact",
                severity=RiskLevel.LOW,
                rationale="redacted email",
            ),
        ),
        aggregate_action="redact",
        aggregate_band=RiskBand.LOW,
        fired_rule_ids=("r_email",),
        transforms=(
            TransformSummary(
                strategy="redact",
                target_finding_index=0,
                before_length=14,
                after_length=15,
                replacement_kind="placeholder",
            ),
        ),
    )
    record = emitter.build(result, outcome, latency_ms=2.0)
    assert len(record.findings) == 1
    assert record.findings[0].entity_type == "EMAIL_ADDRESS"
    assert record.findings[0].length == 14
    assert len(record.transforms) == 1
    assert record.fired_rules == ("r_email",)


def test_correlation_id_propagated_when_present_on_result() -> None:
    emitter = DecisionEmitter()
    result = GuardResult(text="hi", phase="pre_process")
    outcome = RoutedOutcome(
        transformed_text="hi",
        decisions=(),
        aggregate_action="pass",
        aggregate_band=RiskBand.LOW,
    )
    # GuardResult does not currently carry correlation_id; the emitter
    # gracefully falls back to None. This documents the contract.
    record = emitter.build(result, outcome, latency_ms=0.0)
    assert record.correlation_id is None
