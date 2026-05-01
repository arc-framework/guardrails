"""T069 — TokenizeStrategy unit tests."""

from __future__ import annotations

from arc_guard_core.types import Finding, RiskLevel

from arc_guard.strategies.tokenize import TokenizeStrategy


def _f(et: str, start: int, end: int) -> Finding:
    return Finding(et, start, end, RiskLevel.LOW, "stub")


def test_single_occurrence_per_type() -> None:
    text = "card 4111111111111111"
    findings = (_f("CREDIT_CARD", 5, 21),)
    out, decisions = TokenizeStrategy().apply(text, findings)
    assert out == "card [CREDIT_CARD_TOK_1]"
    assert decisions[0].strategy == "tokenize"


def test_multiple_occurrences_sequential_index() -> None:
    text = "1111-1111-1111-1111 2222-2222-2222-2222"
    findings = (
        _f("CREDIT_CARD", 0, 19),
        _f("CREDIT_CARD", 20, 39),
    )
    out, _decisions = TokenizeStrategy().apply(text, findings)
    assert out == "[CREDIT_CARD_TOK_1] [CREDIT_CARD_TOK_2]"


def test_per_input_determinism_within_same_run() -> None:
    """Same input → same tokens. Cross-run determinism is NOT promised."""
    text = "alice@acme.com"
    findings = (_f("EMAIL_ADDRESS", 0, 14),)
    out1, _ = TokenizeStrategy().apply(text, findings)
    out2, _ = TokenizeStrategy().apply(text, findings)
    assert out1 == out2


def test_independent_per_type_counters() -> None:
    text = "alice@acme.com 4111111111111111 bob@acme.com"
    findings = (
        _f("EMAIL_ADDRESS", 0, 14),
        _f("CREDIT_CARD", 15, 31),
        _f("EMAIL_ADDRESS", 32, 44),
    )
    out, _decisions = TokenizeStrategy().apply(text, findings)
    # EMAIL_ADDRESS has two → suffixed _TOK_1 / _TOK_2; CREDIT_CARD has one → _TOK_1
    assert "[EMAIL_ADDRESS_TOK_1]" in out
    assert "[EMAIL_ADDRESS_TOK_2]" in out
    assert "[CREDIT_CARD_TOK_1]" in out
