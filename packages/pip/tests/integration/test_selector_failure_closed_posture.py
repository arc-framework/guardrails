"""Integration test: selector exceptions trigger closed-posture refusal.

A custom selector whose ``select()`` raises must NOT propagate the
original exception to the caller. The router wraps the failure into a
``StrategyError`` (whose ``__cause__`` is the original exception so
lifecycle observers can capture it) and the pipeline converts that into
a refusal envelope.

Two layers are exercised:

1. Router-internal — ``_resolve_strategy_name`` raises a
   ``StrategyError`` whose ``__cause__`` is the original ``RuntimeError``;
   ``StrategyError`` maps to ``RefusalCode.STRATEGY_FAILED`` via the
   ``FAIL_RULE`` table.
2. Full pipeline — ``GuardPipeline.pre_process`` produces a refusal
   envelope and ``action='block'``; no exception escapes the public API.
"""

from __future__ import annotations

import asyncio

import pytest
from arc_guard_core.exceptions import StrategyError
from arc_guard_core.policy import PolicyRule, PolicyRuleSet
from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.types import Finding, GuardInput, GuardResult, RiskLevel

from arc_guard.pipeline import GuardPipeline
from arc_guard.policy.router import RuleBasedPolicyRouter
from arc_guard.selectors.registry import _reset_for_testing as _reset_selectors
from arc_guard.selectors.registry import register_selector


class _RaisingSelector:
    def select(self, finding: Finding, guard_result: GuardResult) -> str:  # noqa: ARG002
        raise RuntimeError("selector blew up on purpose")


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


@pytest.fixture(autouse=True)
def _reset() -> None:
    _reset_selectors()


def test_router_wraps_selector_exception_in_strategy_error() -> None:
    register_selector("test_raising_router", _RaisingSelector())
    router = RuleBasedPolicyRouter()
    rule = PolicyRule(
        id="r_raise",
        match="EMAIL_ADDRESS",
        selector="test_raising_router",
    )
    finding = Finding("EMAIL_ADDRESS", 0, 5, RiskLevel.MEDIUM, "stub")
    result = GuardResult(text="abcde", action="pass", findings=(finding,))

    with pytest.raises(StrategyError) as exc:
        router._resolve_strategy_name(rule, finding, result)

    assert "test_raising_router" in str(exc.value)
    assert "r_raise" in str(exc.value)
    assert isinstance(exc.value.__cause__, RuntimeError)
    assert "selector blew up on purpose" in str(exc.value.__cause__)


def test_strategy_error_maps_to_strategy_failed_refusal_code() -> None:
    from arc_guard_core.failure_modes import lookup_rule

    rule, posture = lookup_rule(StrategyError)
    assert rule.refusal_code == RefusalCode.STRATEGY_FAILED
    assert posture == "closed"


def test_pipeline_returns_refusal_envelope_when_selector_raises() -> None:
    register_selector("test_raising_pipeline", _RaisingSelector())
    ruleset = PolicyRuleSet(
        rules=(
            PolicyRule(
                id="r_raise_pipe",
                match="EMAIL_ADDRESS",
                selector="test_raising_pipeline",
            ),
        ),
    )
    findings = (Finding("EMAIL_ADDRESS", 0, 16, RiskLevel.MEDIUM, "stub"),)
    pipeline = GuardPipeline(
        policy_ruleset=ruleset,
        inspectors=[_StubInspector(findings)],
    )

    result = asyncio.run(pipeline.pre_process(GuardInput(text="a@example.com xy")))

    assert result.refusal is not None
    assert result.action == "block"


def test_pipeline_does_not_propagate_runtime_error_to_caller() -> None:
    register_selector("test_raising_no_leak", _RaisingSelector())
    ruleset = PolicyRuleSet(
        rules=(
            PolicyRule(
                id="r_no_leak",
                match="EMAIL_ADDRESS",
                selector="test_raising_no_leak",
            ),
        ),
    )
    findings = (Finding("EMAIL_ADDRESS", 0, 16, RiskLevel.MEDIUM, "stub"),)
    pipeline = GuardPipeline(
        policy_ruleset=ruleset,
        inspectors=[_StubInspector(findings)],
    )

    result = asyncio.run(pipeline.pre_process(GuardInput(text="a@example.com xy")))

    assert result.action == "block"
    assert result.refusal is not None
