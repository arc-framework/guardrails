"""Typed-placeholder integration: ≥5 entity types end-to-end.

Validates that an input with five distinct entity types yields
exactly five typed placeholders, that two distinct credit-card
numbers yield distinguishable suffixed placeholders, and that benign
input passes through. Asserts zero raw entity bytes (substring length
≥ 4) appear in the output.
"""

from __future__ import annotations

from arc_guard_core.types import Finding, GuardResult, RiskLevel

from arc_guard.strategies.redact import RedactStrategy


def _f(entity_type: str, start: int, end: int, risk: RiskLevel = RiskLevel.LOW) -> Finding:
    return Finding(
        entity_type=entity_type,
        start=start,
        end=end,
        risk_level=risk,
        inspector="test",
    )


# ---------------------------------------------------------------------------
# Acceptance scenario 1 — 5 distinct entity types
# ---------------------------------------------------------------------------


def test_five_distinct_entity_types_yield_five_placeholders() -> None:
    text = (
        "Hello Alice Johnson, email alice@acme.com about project Helios; "
        "card 4111-1111-1111-1111 SSN 123-45-6789"
    )
    findings = (
        _f("EMPLOYEE_NAME", 6, 19),
        _f("EMAIL_ADDRESS", 27, 41),
        _f("INTERNAL_PROJECT", 56, 62),
        _f("CREDIT_CARD", 69, 88),
        _f("US_SSN", 93, 104),
    )
    out, decisions = RedactStrategy().apply(text, findings)

    # Each entity type appears exactly once → all unsuffixed.
    assert "[EMPLOYEE_NAME]" in out
    assert "[EMAIL_ADDRESS]" in out
    assert "[INTERNAL_PROJECT]" in out
    assert "[CREDIT_CARD]" in out
    assert "[US_SSN]" in out

    # Decisions: one per finding, in span order.
    assert len(decisions) == 5

    # Zero raw entity bytes (≥4-char substrings) leaked.
    raw_substrings = [
        "Alice Johnson", "alice@acme", "Helios",
        "4111-1111", "1111-1111", "123-45-6789",
    ]
    for raw in raw_substrings:
        assert raw not in out, f"raw substring leaked: {raw!r} appears in {out!r}"


# ---------------------------------------------------------------------------
# Acceptance scenario 2 — distinguishable suffixed placeholders
# ---------------------------------------------------------------------------


def test_two_distinct_credit_cards_get_distinguishable_placeholders() -> None:
    text = "Cards 4111-1111-1111-1111 and 5555-5555-5555-4444 are different"
    findings = (
        _f("CREDIT_CARD", 6, 25),
        _f("CREDIT_CARD", 30, 49),
    )
    out, decisions = RedactStrategy().apply(text, findings)
    assert out == "Cards [CREDIT_CARD_1] and [CREDIT_CARD_2] are different"
    # Decisions preserve span order
    assert decisions[0].metadata["placeholder"] == "[CREDIT_CARD_1]"
    assert decisions[1].metadata["placeholder"] == "[CREDIT_CARD_2]"
    # Zero raw card digits leak.
    assert "4111" not in out
    assert "5555" not in out


# ---------------------------------------------------------------------------
# Acceptance scenario 3 — benign input
# ---------------------------------------------------------------------------


def test_benign_input_unchanged() -> None:
    text = "What's the weather today?"
    out, decisions = RedactStrategy().apply(text, ())
    assert out == text
    assert decisions == ()


# ---------------------------------------------------------------------------
# GuardResult pipeline-shape compatibility check
# ---------------------------------------------------------------------------


def test_redact_decisions_are_compatible_with_guard_result() -> None:
    text = "alice@acme.com"
    findings = (_f("EMAIL_ADDRESS", 0, 14),)
    out, decisions = RedactStrategy().apply(text, findings)
    # GuardResult accepts the decisions tuple unchanged across the contract layer.
    result = GuardResult(text=out, action="redact", findings=findings, decisions=decisions)
    assert result.text == "[EMAIL_ADDRESS]"
    # Decision references the original finding by index.
    assert result.decisions[0].finding_ids == (0,)
    assert result.decisions[0].strategy == "redact"
