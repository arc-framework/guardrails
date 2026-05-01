"""T041 — Strategy conflict resolution precedence."""

from __future__ import annotations

import pytest
from arc_guard_core.policy import PolicyRule, PolicyRuleSet
from arc_guard_core.types import Finding, GuardResult, RiskLevel

from arc_guard.policy.conflict import STRATEGY_PRECEDENCE, resolve_conflict
from arc_guard.policy.router import RuleBasedPolicyRouter


def _rule(rule_id: str, strategy: str) -> PolicyRule:
    return PolicyRule(id=rule_id, match="EMAIL_ADDRESS", strategy=strategy)


def test_precedence_order() -> None:
    assert STRATEGY_PRECEDENCE == ("block", "redact", "tokenize", "hash", "warn", "pass")


@pytest.mark.parametrize(
    ("a", "b", "expected_winner"),
    [
        ("block", "redact", "block"),
        ("block", "hash", "block"),
        ("block", "warn", "block"),
        ("redact", "hash", "redact"),
        ("redact", "tokenize", "redact"),
        ("redact", "warn", "redact"),
        ("tokenize", "hash", "tokenize"),
        ("tokenize", "warn", "tokenize"),
        ("hash", "warn", "hash"),
        ("warn", "pass", "warn"),
    ],
)
def test_pairwise_precedence(a: str, b: str, expected_winner: str) -> None:
    """Either declaration order — the more-restrictive strategy wins."""
    winner, _ = resolve_conflict([_rule("ra", a), _rule("rb", b)])
    assert winner.strategy == expected_winner

    winner, _ = resolve_conflict([_rule("rb", b), _rule("ra", a)])
    assert winner.strategy == expected_winner


def test_equal_precedence_picks_first_declared() -> None:
    winner, losers = resolve_conflict([_rule("first", "redact"), _rule("second", "redact")])
    assert winner.id == "first"
    assert losers[0].id == "second"


def test_router_records_conflict_resolution_in_rationale() -> None:
    """When two rules match the same finding, the rationale names the override."""
    policy = PolicyRuleSet(
        rules=(
            PolicyRule(id="r_hash_emails", match="EMAIL_ADDRESS", strategy="hash"),
            PolicyRule(id="r_redact_emails", match="EMAIL_ADDRESS", strategy="redact"),
        ),
    )
    findings = (Finding("EMAIL_ADDRESS", 0, 14, RiskLevel.LOW, "stub"),)
    result = GuardResult(text="alice@acme.com", findings=findings, phase="pre_process")
    outcome = RuleBasedPolicyRouter().route(result, policy)
    # Redact wins (more restrictive than hash).
    assert outcome.decisions[0].strategy == "redact"
    rationale = outcome.decisions[0].rationale
    assert "overrode" in rationale
    assert "r_hash_emails" in rationale
    assert "hash" in rationale


def test_resolve_conflict_empty_raises() -> None:
    with pytest.raises(ValueError):
        resolve_conflict([])
