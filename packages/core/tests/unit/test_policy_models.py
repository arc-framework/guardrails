"""Policy model unit tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arc_guard_core.exceptions import ConfigCrossFieldError
from arc_guard_core.policy import (
    PolicyRule,
    PolicyRuleSet,
    RiskBand,
    RiskThresholds,
    RoutedOutcome,
    TransformSummary,
)
from arc_guard_core.types import RiskLevel


def test_risk_band_ordering_via_str() -> None:
    assert RiskBand.LOW.value == "low"
    assert RiskBand.CRITICAL.value == "critical"


def test_risk_thresholds_defaults() -> None:
    rt = RiskThresholds()
    assert rt.low_max_count == 2
    assert rt.medium_max_count == 4
    assert rt.high_escalates_at == 1
    assert rt.critical_escalates_at == 1
    assert rt.soft_pii_aggregation == 3
    assert rt.min_inspectors_for_critical == 1


def test_risk_thresholds_negative_rejected() -> None:
    with pytest.raises(ValidationError):
        RiskThresholds(low_max_count=-1)


def test_risk_thresholds_requires_at_least_one_inspector_for_critical() -> None:
    with pytest.raises(ValidationError):
        RiskThresholds(min_inspectors_for_critical=0)


def test_risk_thresholds_low_must_not_exceed_medium() -> None:
    with pytest.raises(ValidationError):
        RiskThresholds(low_max_count=10, medium_max_count=4)


def test_policy_rule_required_fields() -> None:
    rule = PolicyRule(
        id="r1",
        match="EMAIL_ADDRESS",
        strategy="redact",
    )
    assert rule.id == "r1"
    assert rule.severity_floor == RiskLevel.LOW
    assert rule.refusal_human_message is None


def test_policy_rule_empty_id_rejected() -> None:
    with pytest.raises(ValidationError):
        PolicyRule(id="", match="EMAIL_ADDRESS", strategy="redact")


def test_policy_rule_set_default_action_block_with_no_rules_rejected() -> None:
    with pytest.raises(ConfigCrossFieldError) as excinfo:
        PolicyRuleSet(rules=(), default_action_when_no_rules_fire="block")
    assert "config.cross_field_violation" == excinfo.value.code


def test_policy_rule_set_clarification_critical_rejected() -> None:
    with pytest.raises(ConfigCrossFieldError):
        PolicyRuleSet(
            rules=(PolicyRule(id="r1", match="EMAIL_ADDRESS", strategy="redact"),),
            clarification_enabled=True,
            ambiguous_threshold=RiskBand.CRITICAL,
        )


def test_policy_rule_set_duplicate_id_rejected() -> None:
    with pytest.raises(ConfigCrossFieldError):
        PolicyRuleSet(
            rules=(
                PolicyRule(id="r1", match="EMAIL_ADDRESS", strategy="redact"),
                PolicyRule(id="r1", match="CREDIT_CARD", strategy="hash"),
            )
        )


def test_routed_outcome_default_fields() -> None:
    outcome = RoutedOutcome(
        transformed_text="hi",
        decisions=(),
        aggregate_action="pass",
        aggregate_band=RiskBand.LOW,
    )
    assert outcome.refusal is None
    assert outcome.clarification is None
    assert outcome.fired_rule_ids == ()
    assert outcome.transforms == ()


def test_transform_summary_construction() -> None:
    ts = TransformSummary(
        strategy="redact",
        target_finding_index=0,
        before_length=20,
        after_length=15,
        replacement_kind="placeholder",
    )
    assert ts.metadata == {}
