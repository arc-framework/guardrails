"""Contract test: PolicyRule.selector field + selector/strategy mutex."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arc_guard_core.policy import PolicyRule


def test_legacy_strategy_only_form_parses() -> None:
    r = PolicyRule(id="r1", match="pii.email", strategy="redact")
    assert r.strategy == "redact"
    assert r.selector is None


def test_new_selector_only_form_parses() -> None:
    r = PolicyRule(id="r2", match="pii.email", selector="default")
    assert r.strategy is None
    assert r.selector == "default"


def test_both_set_raises_with_rule_id_in_message() -> None:
    with pytest.raises(ValidationError) as exc:
        PolicyRule(id="rule_x", match="pii.email", strategy="redact", selector="default")
    msg = str(exc.value)
    assert "mutually exclusive" in msg
    assert "rule_x" in msg
    assert "redact" in msg
    assert "default" in msg


def test_neither_set_raises_with_rule_id_in_message() -> None:
    with pytest.raises(ValidationError) as exc:
        PolicyRule(id="rule_y", match="pii.email")
    msg = str(exc.value)
    assert "rule_y" in msg
    assert "must be set" in msg


def test_extra_forbid_still_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        PolicyRule(
            id="r3",
            match="pii.email",
            strategy="redact",
            unknown_field="x",  # type: ignore[call-arg]
        )


def test_strategy_empty_string_rejected_when_set() -> None:
    with pytest.raises(ValidationError):
        PolicyRule(id="r4", match="pii.email", strategy="")


def test_selector_empty_string_rejected_when_set() -> None:
    with pytest.raises(ValidationError):
        PolicyRule(id="r5", match="pii.email", selector="")
