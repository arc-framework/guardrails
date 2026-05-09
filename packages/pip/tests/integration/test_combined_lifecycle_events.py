"""Lifecycle event tagging for combined-capability runs.

Verifies that selector-driven masking decisions carry metadata.selector,
content-policy findings carry metadata.policy + exemplar_set_id, and
code-injection findings carry metadata.fingerprint with the documented
shape.
"""

from __future__ import annotations

import pytest
from arc_guard_core.policy import PolicyRule
from arc_guard_core.protocols import ContentPolicyDecision
from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.types import Finding, GuardResult, RiskLevel

from arc_guard.content_policies.aggregate import (
    build_finding_metadata,
    evaluate_content_policies,
)
from arc_guard.content_policies.registry import (
    _reset_for_testing as _reset_cp,
)
from arc_guard.content_policies.registry import (
    get_content_policy,
    list_registered,
    register_content_policy,
)
from arc_guard.inspectors.code_injection import SqlInjectionInspector
from arc_guard.policy.router import RuleBasedPolicyRouter
from arc_guard.selectors.registry import _reset_for_testing as _reset_sel
from arc_guard.selectors.registry import register_selector


class _FixedSelector:
    def __init__(self, name: str) -> None:
        self._name = name

    def select(self, finding: Finding, guard_result: GuardResult) -> str:  # noqa: ARG002
        return self._name


class _FixedMatchPolicy:
    def __init__(self, name: str) -> None:
        self._name = name

    def evaluate(self, text: str) -> ContentPolicyDecision:  # noqa: ARG002
        return ContentPolicyDecision(
            matched=True,
            confidence=0.88,
            policy_name=self._name,
            refusal_code=RefusalCode.POLICY_BLOCK,
        )


@pytest.fixture(autouse=True)
def _reset() -> None:
    _reset_sel()
    _reset_cp()


def test_selector_decision_metadata_includes_selector_name() -> None:
    register_selector("test_marker", _FixedSelector("redact"))
    router = RuleBasedPolicyRouter()
    rule = PolicyRule(id="r1", match="EMAIL_ADDRESS", selector="test_marker")
    finding = Finding(
        entity_type="EMAIL_ADDRESS",
        start=0,
        end=20,
        risk_level=RiskLevel.MEDIUM,
        inspector="presidio",
    )
    result = GuardResult(text="me@example.com", action="pass", findings=(finding,))
    outcome = router._route(result, _make_ruleset(rule))

    decisions = outcome.decisions
    assert len(decisions) == 1
    assert decisions[0].metadata.get("selector") == "test_marker"
    assert decisions[0].metadata.get("firing_rule_id") == "r1"


def test_content_policy_finding_metadata_carries_policy_name_and_exemplar_id() -> None:
    register_content_policy("p1", _FixedMatchPolicy("p1"))
    policies = [get_content_policy(name) for name in list_registered()]
    firings = evaluate_content_policies("trigger", policies)
    assert len(firings) == 1
    fmeta = build_finding_metadata(firings[0])
    assert fmeta["policy"] == "p1"
    assert "exemplar_set_id" in fmeta
    assert fmeta["similarity"] == 0.88


@pytest.mark.asyncio
async def test_code_injection_finding_metadata_carries_fingerprint() -> None:
    inspector = SqlInjectionInspector()
    attack = "SELECT * FROM users; DROP TABLE users; --"
    post_in = GuardResult(text=attack, action="pass", findings=(), phase="post_process")

    out = await inspector.inspect(post_in)

    assert len(out.findings) >= 1
    fp_meta = out.findings[0].metadata.get("fingerprint")
    assert isinstance(fp_meta, dict)
    assert fp_meta["hash"].startswith("sha256:")
    assert "length_chars" in fp_meta
    assert "char_class" in fp_meta
    # raw_match must be absent under default capture_raw_matches=False
    assert "raw_match" not in out.findings[0].metadata


def _make_ruleset(*rules):  # type: ignore[no-untyped-def]
    from arc_guard_core.policy import PolicyRuleSet

    return PolicyRuleSet(rules=tuple(rules))
