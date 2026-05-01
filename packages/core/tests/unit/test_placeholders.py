"""T023 — typed-placeholder registry tests."""

from __future__ import annotations

import pytest

from arc_guard_core.placeholders import (
    DEFAULT_PLACEHOLDERS,
    format_placeholder,
    get_placeholder,
    list_registered,
    register_placeholder,
)


def test_default_registry_populated() -> None:
    assert "EMAIL_ADDRESS" in DEFAULT_PLACEHOLDERS
    assert "CREDIT_CARD" in DEFAULT_PLACEHOLDERS
    assert get_placeholder("EMAIL_ADDRESS") == "[EMAIL_ADDRESS]"


def test_unknown_entity_synthesises_label() -> None:
    # Spec 001 backward-compat: unknown types fall back to [<TYPE>]
    assert get_placeholder("MY_CUSTOM") == "[MY_CUSTOM]"


def test_format_single_unsuffixed() -> None:
    assert format_placeholder("CREDIT_CARD", 1, 1) == "[CREDIT_CARD]"


def test_format_multi_suffixed() -> None:
    assert format_placeholder("CREDIT_CARD", 1, 2) == "[CREDIT_CARD_1]"
    assert format_placeholder("CREDIT_CARD", 2, 2) == "[CREDIT_CARD_2]"


def test_format_three_occurrences() -> None:
    out = [format_placeholder("EMAIL_ADDRESS", i, 3) for i in range(1, 4)]
    assert out == ["[EMAIL_ADDRESS_1]", "[EMAIL_ADDRESS_2]", "[EMAIL_ADDRESS_3]"]


def test_format_invalid_inputs_rejected() -> None:
    with pytest.raises(ValueError):
        format_placeholder("X", 0, 1)
    with pytest.raises(ValueError):
        format_placeholder("X", 2, 1)
    with pytest.raises(ValueError):
        format_placeholder("X", 1, 0)


def test_register_placeholder_validation() -> None:
    register_placeholder("AADHAAR", "[AADHAAR]")
    assert get_placeholder("AADHAAR") == "[AADHAAR]"
    assert "AADHAAR" in list_registered()

    with pytest.raises(ValueError):
        register_placeholder("X", "lowercase")
    with pytest.raises(ValueError):
        register_placeholder("X", "[has space]")
    with pytest.raises(ValueError):
        register_placeholder("", "[X]")
