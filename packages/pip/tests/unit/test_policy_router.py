"""RuleBasedPolicyRouter unit tests."""

from __future__ import annotations

from arc_guard_core.policy import PolicyRule, PolicyRuleSet
from arc_guard_core.types import Finding, GuardResult, RiskLevel

from arc_guard.policy.router import RuleBasedPolicyRouter


def _f(et: str, start: int, end: int, risk: RiskLevel = RiskLevel.LOW) -> Finding:
    return Finding(et, start, end, risk, "stub")


def _result(text: str, findings: tuple[Finding, ...]) -> GuardResult:
    return GuardResult(text=text, findings=findings, phase="pre_process")


def test_single_rule_single_finding_redact() -> None:
    policy = PolicyRuleSet(
        rules=(PolicyRule(id="r1", match="EMAIL_ADDRESS", strategy="redact"),),
    )
    result = _result("Email alice@acme.com", (_f("EMAIL_ADDRESS", 6, 20),))
    outcome = RuleBasedPolicyRouter().route(result, policy)
    assert outcome.aggregate_action == "redact"
    assert outcome.transformed_text == "Email [EMAIL_ADDRESS]"
    assert len(outcome.decisions) == 1
    assert outcome.decisions[0].strategy == "redact"
    assert outcome.fired_rule_ids == ("r1",)


def test_multiple_rules_each_match_one_finding() -> None:
    policy = PolicyRuleSet(
        rules=(
            PolicyRule(id="r_email", match="EMAIL_ADDRESS", strategy="redact"),
            PolicyRule(id="r_card", match="CREDIT_CARD", strategy="hash", severity_floor=RiskLevel.MEDIUM),
        ),
    )
    findings = (
        _f("EMAIL_ADDRESS", 0, 14),
        _f("CREDIT_CARD", 20, 36, RiskLevel.MEDIUM),
    )
    outcome = RuleBasedPolicyRouter().route(
        _result("alice@acme.com card 4111111111111111", findings), policy
    )
    strategies = [d.strategy for d in outcome.decisions]
    assert sorted(strategies) == sorted(["redact", "hash"])
    assert "[EMAIL_ADDRESS]" in outcome.transformed_text
    assert "[HASH:" in outcome.transformed_text


def test_severity_floor_skips_below_threshold_findings() -> None:
    policy = PolicyRuleSet(
        rules=(
            PolicyRule(
                id="r_high_only",
                match="CREDIT_CARD",
                strategy="block",
                severity_floor=RiskLevel.HIGH,
            ),
        ),
    )
    # Finding is MEDIUM — below the rule's HIGH severity_floor.
    findings = (_f("CREDIT_CARD", 0, 16, RiskLevel.MEDIUM),)
    outcome = RuleBasedPolicyRouter().route(_result("4111111111111111", findings), policy)
    # No rule fired.
    assert outcome.decisions == ()
    assert outcome.fired_rule_ids == ()


def test_no_findings_passes_through() -> None:
    policy = PolicyRuleSet(
        rules=(PolicyRule(id="r1", match="EMAIL_ADDRESS", strategy="redact"),),
    )
    outcome = RuleBasedPolicyRouter().route(_result("hello", ()), policy)
    assert outcome.aggregate_action == "pass"
    assert outcome.decisions == ()


def test_rule_with_unmatched_entity_is_silently_skipped() -> None:
    policy = PolicyRuleSet(
        rules=(
            PolicyRule(id="r_email", match="EMAIL_ADDRESS", strategy="redact"),
            PolicyRule(id="r_phone", match="PHONE_NUMBER", strategy="hash"),
        ),
    )
    findings = (_f("EMAIL_ADDRESS", 0, 14),)
    outcome = RuleBasedPolicyRouter().route(_result("alice@acme.com", findings), policy)
    assert outcome.fired_rule_ids == ("r_email",)


def test_decisions_in_finding_span_order() -> None:
    policy = PolicyRuleSet(
        rules=(
            PolicyRule(id="r_email", match="EMAIL_ADDRESS", strategy="redact"),
            PolicyRule(id="r_card", match="CREDIT_CARD", strategy="hash"),
        ),
    )
    # CREDIT_CARD appears before EMAIL_ADDRESS in span order
    findings = (
        _f("CREDIT_CARD", 0, 16),
        _f("EMAIL_ADDRESS", 20, 34),
    )
    outcome = RuleBasedPolicyRouter().route(
        _result("4111111111111111 abc alice@acme.com", findings), policy
    )
    decisions_in_order = [d.strategy for d in outcome.decisions]
    assert decisions_in_order == ["hash", "redact"]
