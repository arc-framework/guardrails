"""Composable-routing fixture suite covering ≥8 (rules × input) combinations."""

from __future__ import annotations

import asyncio

import pytest
from arc_guard_core.policy import PolicyRule, PolicyRuleSet
from arc_guard_core.types import Finding, GuardInput, GuardResult, RiskLevel

from arc_guard.pipeline import GuardPipeline


class _StubInspector:
    name = "stub"

    def __init__(self, findings: tuple[Finding, ...]) -> None:
        self._findings = findings

    async def inspect(self, result: GuardResult) -> GuardResult:
        return GuardResult(
            text=result.text,
            action=result.action,
            findings=tuple(result.findings) + self._findings,
            phase=result.phase,
        )


def _f(et: str, start: int, end: int, risk: RiskLevel = RiskLevel.LOW) -> Finding:
    return Finding(et, start, end, risk, "stub")


# Each row: (case_id, ruleset, text, findings, expected_decision_count, expected_aggregate_action)
CASES = [
    # 1. 4 rules / all 4 fire
    (
        "all_four_fire",
        PolicyRuleSet(
            rules=(
                PolicyRule(id="r1", match="EMAIL_ADDRESS", strategy="redact"),
                PolicyRule(id="r2", match="CREDIT_CARD", strategy="hash"),
                PolicyRule(id="r3", match="US_SSN", strategy="redact"),
                PolicyRule(id="r4", match="CUSTOMER_NAME", strategy="warn"),
            ),
        ),
        "alice@acme.com 4111111111111111 123-45-6789 Bob",
        (
            _f("EMAIL_ADDRESS", 0, 14),
            _f("CREDIT_CARD", 15, 31, RiskLevel.MEDIUM),
            _f("US_SSN", 32, 43, RiskLevel.HIGH),
            _f("CUSTOMER_NAME", 44, 47),
        ),
        4,
        "redact",  # HIGH band → not block; redact most-restrictive non-block
    ),
    # 2. 4 rules / 2 fire
    (
        "two_of_four_fire",
        PolicyRuleSet(
            rules=(
                PolicyRule(id="r1", match="EMAIL_ADDRESS", strategy="redact"),
                PolicyRule(id="r2", match="CREDIT_CARD", strategy="hash"),
                PolicyRule(id="r3", match="US_SSN", strategy="redact"),
                PolicyRule(
                    id="r4", match="INJECTION", strategy="block", severity_floor=RiskLevel.HIGH
                ),
            ),
        ),
        "alice@acme.com card 4111111111111111",
        (
            _f("EMAIL_ADDRESS", 0, 14),
            _f("CREDIT_CARD", 20, 36, RiskLevel.MEDIUM),
        ),
        2,
        # Precedence: redact (1) > hash (3). Redact is more restrictive.
        "redact",
    ),
    # 3. 4 rules / 0 fire
    (
        "no_rules_fire",
        PolicyRuleSet(
            rules=(
                PolicyRule(id="r1", match="EMAIL_ADDRESS", strategy="redact"),
                PolicyRule(id="r2", match="CREDIT_CARD", strategy="hash"),
                PolicyRule(id="r3", match="US_SSN", strategy="redact"),
                PolicyRule(id="r4", match="INJECTION", strategy="block"),
            ),
        ),
        "hello world",
        (),
        0,
        "pass",
    ),
    # 4. Overlapping rules same finding (conflict resolution)
    (
        "overlapping_conflict",
        PolicyRuleSet(
            rules=(
                PolicyRule(id="r_warn", match="EMAIL_ADDRESS", strategy="warn"),
                PolicyRule(id="r_redact", match="EMAIL_ADDRESS", strategy="redact"),
                PolicyRule(id="r_hash", match="EMAIL_ADDRESS", strategy="hash"),
            ),
        ),
        "alice@acme.com",
        (_f("EMAIL_ADDRESS", 0, 14),),
        1,  # Conflict resolved → one decision (the winning rule)
        "redact",  # most restrictive
    ),
    # 5. Severity floor skips below-threshold finding
    (
        "severity_floor_skips",
        PolicyRuleSet(
            rules=(
                PolicyRule(
                    id="r_high",
                    match="CREDIT_CARD",
                    strategy="block",
                    severity_floor=RiskLevel.HIGH,
                ),
            ),
        ),
        "card 4111111111111111",
        (_f("CREDIT_CARD", 5, 21, RiskLevel.MEDIUM),),
        0,
        "pass",
    ),
    # 6. Two findings of same type with one matching rule
    (
        "two_findings_one_rule",
        PolicyRuleSet(
            rules=(PolicyRule(id="r_email", match="EMAIL_ADDRESS", strategy="redact"),),
        ),
        "alice@acme.com or bob@acme.com",
        (
            _f("EMAIL_ADDRESS", 0, 14),
            _f("EMAIL_ADDRESS", 18, 30),
        ),
        2,  # One decision per matching finding
        "redact",
    ),
    # 7. Empty rules + default_action_when_no_rules_fire="pass"
    (
        "empty_rules_pass_default",
        PolicyRuleSet(
            rules=(),
            default_action_when_no_rules_fire="pass",
        ),
        "any text",
        (_f("EMAIL_ADDRESS", 0, 8),),
        0,
        "pass",  # No rules → default pass
    ),
    # 8. Equal precedence resolves by declaration order
    (
        "equal_precedence_first_wins",
        PolicyRuleSet(
            rules=(
                PolicyRule(id="r_first_redact", match="EMAIL_ADDRESS", strategy="redact"),
                PolicyRule(id="r_second_redact", match="EMAIL_ADDRESS", strategy="redact"),
            ),
        ),
        "alice@acme.com",
        (_f("EMAIL_ADDRESS", 0, 14),),
        1,
        "redact",
    ),
]


@pytest.mark.parametrize(
    ("case_id", "ruleset", "text", "findings", "expected_decisions", "expected_action"),
    CASES,
    ids=[c[0] for c in CASES],
)
def test_policy_combinations(
    case_id: str,
    ruleset: PolicyRuleSet,
    text: str,
    findings: tuple[Finding, ...],
    expected_decisions: int,
    expected_action: str,
) -> None:
    pipeline = GuardPipeline(
        policy_ruleset=ruleset,
        inspectors=[_StubInspector(findings)],
    )
    result = asyncio.run(pipeline.pre_process(GuardInput(text=text)))
    assert len(result.decisions) == expected_decisions, (
        f"{case_id}: expected {expected_decisions} decisions, got {len(result.decisions)}"
    )
    assert result.action == expected_action, (
        f"{case_id}: expected action {expected_action!r}, got {result.action!r}"
    )
