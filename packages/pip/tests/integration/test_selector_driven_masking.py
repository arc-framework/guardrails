"""Integration test: selector: default drives per-entity strategy choice.

Mirrors the User Story 1 Independent Test: a policy whose rules use
``selector: default`` produces a decision record with one strategy per
entity type, each chosen by the bundled DefaultStrategySelector, and
every decision is attributed to the rule that fired it.

Tested through the RuleBasedPolicyRouter rather than the full pipeline
because:

- The router is the integration point for selector resolution.
- Constructing a real PresidioInspector chain that emits five distinct
  entity types in a single request is brittle and not the point of this
  test (selector-driven masking is router-level behavior).
"""

from __future__ import annotations

from arc_guard_core.policy import PolicyRule, PolicyRuleSet
from arc_guard_core.types import Finding, GuardResult, RiskLevel

from arc_guard.policy.router import RuleBasedPolicyRouter
from arc_guard.selectors.default import DefaultStrategySelector


def _finding(entity_type: str, start: int, end: int) -> Finding:
    return Finding(
        entity_type=entity_type,
        start=start,
        end=end,
        risk_level=RiskLevel.MEDIUM,
        inspector="test",
    )


def test_selector_default_picks_per_entity_strategy() -> None:
    text = (
        "email user@example.com card 4111111111111111 ssn 123-45-6789 url https://x.test emp E12345"
    )
    findings = (
        _finding("EMAIL_ADDRESS", 6, 22),
        _finding("CREDIT_CARD", 28, 44),
        _finding("US_SSN", 49, 60),
        _finding("URL", 65, 79),
        _finding("EMPLOYEE_ID", 84, 90),
    )
    result = GuardResult(text=text, action="pass", findings=findings)

    ruleset = PolicyRuleSet(
        rules=(
            PolicyRule(id="r_email", match="EMAIL_ADDRESS", selector="default"),
            PolicyRule(id="r_card", match="CREDIT_CARD", selector="default"),
            PolicyRule(id="r_ssn", match="US_SSN", selector="default"),
            PolicyRule(id="r_url", match="URL", selector="default"),
            PolicyRule(id="r_emp", match="EMPLOYEE_ID", selector="default"),
        ),
    )

    router = RuleBasedPolicyRouter()
    outcome = router.route(result, ruleset)

    expected_per_entity = {
        "EMAIL_ADDRESS": "redact",
        "CREDIT_CARD": "block",
        "US_SSN": "hash",
        "URL": "warn",
        "EMPLOYEE_ID": "tokenize",
    }

    assert len(outcome.decisions) == 5
    decisions_by_entity = {findings[d.finding_ids[0]].entity_type: d for d in outcome.decisions}
    for entity_type, expected_strategy in expected_per_entity.items():
        decision = decisions_by_entity[entity_type]
        assert decision.strategy == expected_strategy
        assert decision.metadata.get("selector") == "default"

    expected_rule_ids = {"r_email", "r_card", "r_ssn", "r_url", "r_emp"}
    actual_rule_ids = {d.metadata.get("firing_rule_id") for d in outcome.decisions}
    assert actual_rule_ids == expected_rule_ids

    expected_transform_strategies = set(expected_per_entity.values())
    actual_transform_strategies = {t.strategy for t in outcome.transforms}
    assert actual_transform_strategies == expected_transform_strategies


def test_default_selector_matches_documented_choices_for_all_classes() -> None:
    selector = DefaultStrategySelector()
    pairs = [
        ("EMAIL_ADDRESS", "redact"),
        ("CREDIT_CARD", "block"),
        ("US_SSN", "hash"),
        ("URL", "warn"),
        ("EMPLOYEE_ID", "tokenize"),
    ]
    for entity_type, expected in pairs:
        finding = _finding(entity_type, 0, 1)
        result = GuardResult(text="x", action="pass", findings=(finding,))
        assert selector.select(finding, result) == expected
