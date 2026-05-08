"""Integration test: pipeline route stage resolves PolicyRule.selector.

Validates the foundational selector-resolution path: a rule with `selector`
instead of `strategy` causes the pipeline to look up the selector by name,
invoke `selector.select(finding, guard_result)`, validate the returned
strategy name against the strategy registry, and apply it.

Negative paths:
- Selector returns an unregistered strategy name -> StrategyError.
- Selector raises -> closed-posture refusal via PipelineContractValidationError.
- Rule references unknown selector -> ConfigCrossFieldError at validation.
"""

from __future__ import annotations

import pytest

from arc_guard_core.exceptions import (
    ConfigCrossFieldError,
    StrategyError,
)
from arc_guard_core.policy import PolicyRule, PolicyRuleSet
from arc_guard_core.types import Finding, GuardResult, RiskLevel

from arc_guard.policy.router import RuleBasedPolicyRouter
from arc_guard.selectors.registry import _reset_for_testing as _reset_selectors
from arc_guard.selectors.registry import register_selector


class _FixedSelector:
    """Selector that always returns the same strategy name."""

    def __init__(self, name: str) -> None:
        self._name = name

    def select(self, finding: Finding, guard_result: GuardResult) -> str:  # noqa: ARG002
        return self._name


class _RaisingSelector:
    def select(self, finding: Finding, guard_result: GuardResult) -> str:  # noqa: ARG002
        raise RuntimeError("simulated selector failure")


@pytest.fixture(autouse=True)
def _reset() -> None:
    _reset_selectors()


def _make_finding(entity_type: str = "EMAIL_ADDRESS") -> Finding:
    return Finding(
        entity_type=entity_type,
        start=0,
        end=10,
        risk_level=RiskLevel.MEDIUM,
        inspector="test",
    )


def _make_result(text: str, finding: Finding) -> GuardResult:
    return GuardResult(text=text, action="pass", findings=(finding,))


def test_selector_returns_registered_strategy_name() -> None:
    register_selector("test_fixed", _FixedSelector("redact"))
    router = RuleBasedPolicyRouter()
    rule = PolicyRule(id="r1", match="EMAIL_ADDRESS", selector="test_fixed")
    finding = _make_finding()
    result = _make_result("user@example.com", finding)

    strategy_name = router._resolve_strategy_name(rule, finding, result)

    assert strategy_name == "redact"


def test_legacy_strategy_form_short_circuits_selector_lookup() -> None:
    router = RuleBasedPolicyRouter()
    rule = PolicyRule(id="r2", match="EMAIL_ADDRESS", strategy="hash")
    finding = _make_finding()
    result = _make_result("user@example.com", finding)

    strategy_name = router._resolve_strategy_name(rule, finding, result)

    assert strategy_name == "hash"


def test_unknown_selector_raises_config_error() -> None:
    router = RuleBasedPolicyRouter()
    rule = PolicyRule(id="r3", match="EMAIL_ADDRESS", selector="not_registered")
    finding = _make_finding()
    result = _make_result("user@example.com", finding)

    with pytest.raises(ConfigCrossFieldError) as exc:
        router._resolve_strategy_name(rule, finding, result)

    assert "not_registered" in str(exc.value)
    assert "r3" in str(exc.value)


def test_unknown_strategy_returned_by_selector_raises_strategy_error() -> None:
    register_selector("test_returns_unknown", _FixedSelector("not_a_real_strategy"))
    router = RuleBasedPolicyRouter()
    rule = PolicyRule(id="r4", match="EMAIL_ADDRESS", selector="test_returns_unknown")
    finding = _make_finding()
    result = _make_result("user@example.com", finding)

    with pytest.raises(StrategyError) as exc:
        router._resolve_strategy_name(rule, finding, result)

    assert "not_a_real_strategy" in str(exc.value)


def test_selector_exception_wraps_into_strategy_error() -> None:
    # Selector exceptions must trigger closed-posture failure: the wrapped
    # StrategyError maps to RefusalCode.STRATEGY_FAILED via the FAIL_RULE
    # table, producing a refusal envelope at the pipeline boundary.
    register_selector("test_raising", _RaisingSelector())
    router = RuleBasedPolicyRouter()
    rule = PolicyRule(id="r5", match="EMAIL_ADDRESS", selector="test_raising")
    finding = _make_finding()
    result = _make_result("user@example.com", finding)

    with pytest.raises(StrategyError) as exc:
        router._resolve_strategy_name(rule, finding, result)

    assert "test_raising" in str(exc.value)
    assert isinstance(exc.value.__cause__, RuntimeError)


def test_validator_accepts_ruleset_with_selector_rule() -> None:
    register_selector("test_for_validator", _FixedSelector("redact"))
    from arc_guard.policy import validate_strategies_registered

    ruleset = PolicyRuleSet(
        rules=(
            PolicyRule(id="r6", match="EMAIL_ADDRESS", selector="test_for_validator"),
        )
    )
    # Must not raise.
    validate_strategies_registered(ruleset)


def test_validator_rejects_ruleset_with_unknown_selector() -> None:
    from arc_guard.policy import validate_strategies_registered

    ruleset = PolicyRuleSet(
        rules=(
            PolicyRule(id="r7", match="EMAIL_ADDRESS", selector="absent_selector"),
        )
    )
    with pytest.raises(ConfigCrossFieldError) as exc:
        validate_strategies_registered(ruleset)

    assert "absent_selector" in str(exc.value)
