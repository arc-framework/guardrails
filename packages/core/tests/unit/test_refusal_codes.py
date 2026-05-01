"""Unit tests for the RefusalCode registry (T018)."""

from __future__ import annotations

from arc_guard_core.refusal.codes import RefusalCode


def test_codes_are_unique() -> None:
    values = [c.value for c in RefusalCode]
    assert len(values) == len(set(values)), "duplicate refusal code value"


def test_codes_addressable_by_name() -> None:
    assert RefusalCode.JAILBREAK.value == "jailbreak"
    assert RefusalCode.PII_CRITICAL.value == "pii_critical"
    assert RefusalCode.STRATEGY_FAILED.value == "strategy_failed"


def test_codes_are_strings() -> None:
    for code in RefusalCode:
        assert isinstance(code, str)
