"""Typed-placeholder format suite."""

from __future__ import annotations

from arc_guard_core.types import Finding, RiskLevel

from arc_guard.strategies.redact import RedactStrategy


def _f(entity_type: str, start: int, end: int) -> Finding:
    return Finding(
        entity_type=entity_type,
        start=start,
        end=end,
        risk_level=RiskLevel.LOW,
        inspector="test",
    )


def test_single_occurrence_unsuffixed() -> None:
    text = "Email alice@acme.com please"
    findings = (_f("EMAIL_ADDRESS", 6, 20),)
    out, _decisions = RedactStrategy().apply(text, findings)
    assert out == "Email [EMAIL_ADDRESS] please"


def test_two_occurrences_suffixed() -> None:
    text = "alice@acme.com or bob@acme.com"
    findings = (
        _f("EMAIL_ADDRESS", 0, 14),
        _f("EMAIL_ADDRESS", 18, 30),
    )
    out, _ = RedactStrategy().apply(text, findings)
    assert out == "[EMAIL_ADDRESS_1] or [EMAIL_ADDRESS_2]"


def test_three_occurrences_suffixed() -> None:
    text = "1111-1111-1111-1111 2222-2222-2222-2222 3333-3333-3333-3333"
    findings = (
        _f("CREDIT_CARD", 0, 19),
        _f("CREDIT_CARD", 20, 39),
        _f("CREDIT_CARD", 40, 59),
    )
    out, _ = RedactStrategy().apply(text, findings)
    assert out == "[CREDIT_CARD_1] [CREDIT_CARD_2] [CREDIT_CARD_3]"


def test_mixed_types_independent_counters() -> None:
    text = "alice@acme.com 1111-1111-1111-1111 2222-2222-2222-2222"
    findings = (
        _f("EMAIL_ADDRESS", 0, 14),
        _f("CREDIT_CARD", 15, 34),
        _f("CREDIT_CARD", 35, 54),
    )
    out, _ = RedactStrategy().apply(text, findings)
    # EMAIL_ADDRESS occurs once → unsuffixed; CREDIT_CARD occurs twice → suffixed
    assert out == "[EMAIL_ADDRESS] [CREDIT_CARD_1] [CREDIT_CARD_2]"


def test_custom_registered_type_single() -> None:
    from arc_guard_core.placeholders import register_placeholder
    register_placeholder("INTERNAL_TICKET", "[INTERNAL_TICKET]")
    text = "ticket TKT-1234"
    findings = (_f("INTERNAL_TICKET", 7, 15),)
    out, _ = RedactStrategy().apply(text, findings)
    assert out == "ticket [INTERNAL_TICKET]"


def test_custom_registered_type_multi() -> None:
    from arc_guard_core.placeholders import register_placeholder
    register_placeholder("INTERNAL_TICKET", "[INTERNAL_TICKET]")
    text = "TKT-1 and TKT-2"
    findings = (
        _f("INTERNAL_TICKET", 0, 5),
        _f("INTERNAL_TICKET", 10, 15),
    )
    out, _ = RedactStrategy().apply(text, findings)
    assert out == "[INTERNAL_TICKET_1] and [INTERNAL_TICKET_2]"


def test_unregistered_type_falls_back_to_synthetic_label() -> None:
    text = "secret"
    findings = (_f("MY_NEW_TYPE", 0, 6),)
    out, _ = RedactStrategy().apply(text, findings)
    assert out == "[MY_NEW_TYPE]"
