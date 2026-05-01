"""Policy validation rejects unknown strategies and entity types."""

from __future__ import annotations

import pytest
from arc_guard_core.exceptions import ConfigCrossFieldError
from arc_guard_core.policy import PolicyRule, PolicyRuleSet

from arc_guard.pipeline import GuardPipeline
from arc_guard.policy import validate_strategies_registered


def test_unknown_strategy_rejected_at_pipeline_construction() -> None:
    policy = PolicyRuleSet(
        rules=(PolicyRule(id="r1", match="EMAIL_ADDRESS", strategy="not_a_strategy"),),
    )
    with pytest.raises(ConfigCrossFieldError) as excinfo:
        GuardPipeline(policy_ruleset=policy)
    assert excinfo.value.code == "config.cross_field_violation"
    assert excinfo.value.details["rule_id"] == "r1"
    assert excinfo.value.details["strategy"] == "not_a_strategy"


def test_validate_strategies_registered_passes_for_built_ins() -> None:
    policy = PolicyRuleSet(
        rules=(
            PolicyRule(id="r1", match="EMAIL_ADDRESS", strategy="redact"),
            PolicyRule(id="r2", match="CREDIT_CARD", strategy="hash"),
            PolicyRule(id="r3", match="INJECTION", strategy="block"),
            PolicyRule(id="r4", match="CUSTOMER_NAME", strategy="warn"),
            PolicyRule(id="r5", match="US_SSN", strategy="tokenize"),
        ),
    )
    validate_strategies_registered(policy)  # must not raise


def test_empty_rules_with_block_default_rejected_at_model_validation() -> None:
    with pytest.raises(ConfigCrossFieldError):
        PolicyRuleSet(rules=(), default_action_when_no_rules_fire="block")


def test_clarification_with_critical_threshold_rejected() -> None:
    from arc_guard_core.policy import RiskBand

    with pytest.raises(ConfigCrossFieldError):
        PolicyRuleSet(
            rules=(PolicyRule(id="r1", match="EMAIL_ADDRESS", strategy="redact"),),
            clarification_enabled=True,
            ambiguous_threshold=RiskBand.CRITICAL,
        )
