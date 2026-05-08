"""Integration test: PolicyRule selector / strategy validation errors.

Three scenarios:

- Both ``selector`` and ``strategy`` set on a ``PolicyRule`` raises
  ``ValidationError`` at model construction; the error message names
  the rule id so operators can find the offending rule.
- Neither ``selector`` nor ``strategy`` set raises the same way.
- Unknown selector name on a rule passes ``PolicyRule`` construction
  but ``validate_strategies_registered`` rejects the ruleset with a
  ``ConfigCrossFieldError`` whose details include the rule id and the
  unresolved selector name.
"""

from __future__ import annotations

import pytest
from arc_guard_core.exceptions import ConfigCrossFieldError
from arc_guard_core.policy import PolicyRule, PolicyRuleSet
from pydantic import ValidationError

from arc_guard.policy import validate_strategies_registered


def test_rule_with_both_strategy_and_selector_raises_at_construction() -> None:
    with pytest.raises(ValidationError) as exc:
        PolicyRule(
            id="r_both",
            match="EMAIL_ADDRESS",
            strategy="redact",
            selector="default",
        )
    message = str(exc.value)
    assert "r_both" in message
    assert "mutually exclusive" in message
    assert "strategy" in message
    assert "selector" in message


def test_rule_with_neither_strategy_nor_selector_raises_at_construction() -> None:
    with pytest.raises(ValidationError) as exc:
        PolicyRule(id="r_neither", match="EMAIL_ADDRESS")
    message = str(exc.value)
    assert "r_neither" in message
    assert "exactly one" in message
    assert "strategy" in message
    assert "selector" in message


def test_unknown_selector_in_ruleset_raises_config_cross_field_error() -> None:
    ruleset = PolicyRuleSet(
        rules=(
            PolicyRule(
                id="r_unknown_selector",
                match="EMAIL_ADDRESS",
                selector="not_a_real_selector",
            ),
        ),
    )

    with pytest.raises(ConfigCrossFieldError) as exc:
        validate_strategies_registered(ruleset)

    assert "r_unknown_selector" in str(exc.value)
    assert "not_a_real_selector" in str(exc.value)
    assert exc.value.details["rule_id"] == "r_unknown_selector"
    assert exc.value.details["selector"] == "not_a_real_selector"


def test_unknown_strategy_in_ruleset_raises_config_cross_field_error() -> None:
    ruleset = PolicyRuleSet(
        rules=(
            PolicyRule(
                id="r_unknown_strategy",
                match="EMAIL_ADDRESS",
                strategy="not_a_real_strategy",
            ),
        ),
    )

    with pytest.raises(ConfigCrossFieldError) as exc:
        validate_strategies_registered(ruleset)

    assert "r_unknown_strategy" in str(exc.value)
    assert "not_a_real_strategy" in str(exc.value)
