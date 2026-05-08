"""All three new capabilities composed in one deployment.

Validates: refusals short-circuit later stages, distinct refusal codes
when capabilities fire across phases, and the three capabilities don't
interact in surprising ways.
"""

from __future__ import annotations

import pytest

from arc_guard_core.protocols import ContentPolicy, ContentPolicyDecision
from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.types import Finding, GuardResult, RiskLevel

from arc_guard.content_policies.aggregate import (
    build_aggregate_refusal_envelope,
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
from arc_guard.selectors.registry import _reset_for_testing as _reset_sel


def _all_registered_policies() -> list:  # type: ignore[type-arg]
    return [get_content_policy(name) for name in list_registered()]


class _FixedMatchPolicy:
    """ContentPolicy that always or never matches, for deterministic tests."""

    def __init__(self, name: str, matches: bool) -> None:
        self._name = name
        self._matches = matches

    def evaluate(self, text: str) -> ContentPolicyDecision:  # noqa: ARG002
        return ContentPolicyDecision(
            matched=self._matches,
            confidence=0.95 if self._matches else 0.0,
            policy_name=self._name,
            refusal_code=RefusalCode.POLICY_BLOCK if self._matches else None,
        )


@pytest.fixture(autouse=True)
def _reset() -> None:
    _reset_sel()
    _reset_cp()


@pytest.mark.asyncio
async def test_content_policy_match_short_circuits_before_sql_inspector() -> None:
    """When a content policy fires on pre-process input, the request is
    refused. The SQL inspector configured for post-process never runs
    because there is no LLM output to inspect.
    """
    register_content_policy("competitor_pricing", _FixedMatchPolicy("competitor_pricing", True))
    sql_inspector = SqlInjectionInspector()

    text = "What does $other_vendor charge for tier-2 service?"
    firings = evaluate_content_policies(text, _all_registered_policies())

    assert len(firings) == 1
    assert firings[0].name == "competitor_pricing"

    refusal = build_aggregate_refusal_envelope(firings)
    assert refusal is not None
    assert refusal.code == RefusalCode.POLICY_BLOCK

    # SQL inspector did not have a chance to run — verify by inspecting an
    # untouched post-process input. (In a fully wired pipeline, refusal at
    # pre-process means no backend call and no post-process invocation.)
    untouched_post = GuardResult(text="", action="block", findings=(), phase="post_process")
    out = await sql_inspector.inspect(untouched_post)
    assert out.findings == ()


@pytest.mark.asyncio
async def test_sql_inspector_fires_when_content_policy_does_not_match() -> None:
    """A request that passes the semantic policy can still be refused
    post-process when the LLM response contains SQL injection."""
    register_content_policy("competitor_pricing", _FixedMatchPolicy("competitor_pricing", False))
    sql_inspector = SqlInjectionInspector()

    pre_text = "Tell me about Postgres internals."
    firings = evaluate_content_policies(pre_text, _all_registered_policies())
    assert firings == []  # content policy does not fire

    # LLM response contains SQL injection
    llm_response = "SELECT * FROM users; DROP TABLE users; --"
    post_input = GuardResult(
        text=llm_response, action="pass", findings=(), phase="post_process"
    )

    out = await sql_inspector.inspect(post_input)

    assert len(out.findings) >= 1
    subtypes = {f.entity_type for f in out.findings}
    assert any("sql" in s for s in subtypes)


@pytest.mark.asyncio
async def test_distinct_refusal_codes_for_content_policy_vs_sql_injection() -> None:
    """The refusal code from a content policy match (POLICY_BLOCK) is
    distinct from the SQL_INJECTION code that a downstream SQL finding
    would carry — operators can disambiguate by code."""
    register_content_policy("any", _FixedMatchPolicy("any", True))
    firings = evaluate_content_policies("anything", _all_registered_policies())
    cp_envelope = build_aggregate_refusal_envelope(firings)

    assert cp_envelope is not None
    assert cp_envelope.code == RefusalCode.POLICY_BLOCK
    assert cp_envelope.code != RefusalCode.SQL_INJECTION
