"""Uncategorized exceptions are wrapped per the no-leak contract.

A synthetic exception that has no MRO match in ``FAIL_RULE`` falls
through to the unknown rule (posture=closed, severity=critical,
refusal_code=INTERNAL_UNKNOWN_ERROR). The pipeline never re-raises the
original across the public API; instead it surfaces a typed
``GuardResult`` with the unknown-error refusal envelope.
"""

from __future__ import annotations

import pytest
from arc_guard_core.failure_modes import lookup_rule
from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.types import GuardInput

from arc_guard.observability import (
    RecordingLogger,
    RecordingMetricSink,
    RecordingTracer,
)
from arc_guard.pipeline import GuardPipeline


class _MyAppError(Exception):
    """Application-defined exception not in the foundation hierarchy."""


class _RaisingPolicyRouter:
    """Policy router that raises a synthetic error not in FAIL_RULE."""

    def route(self, result, ruleset):  # type: ignore[no-untyped-def]
        raise _MyAppError("synthetic uncategorized failure")


@pytest.mark.asyncio
async def test_unknown_exception_lookup_falls_through_to_unknown_rule() -> None:
    """``lookup_rule`` returns the UNKNOWN_RULE for an MRO-miss exception."""
    rule, posture = lookup_rule(_MyAppError)
    assert rule.failure_class == "unknown"
    assert rule.severity == "critical"
    assert rule.refusal_code == RefusalCode.INTERNAL_UNKNOWN_ERROR
    assert posture == "closed"


@pytest.mark.asyncio
async def test_pipeline_wraps_unknown_exception_in_critical_refusal() -> None:
    """When an uncategorized exception escapes a closed-posture stage, the
    pipeline produces a refusal envelope with INTERNAL_UNKNOWN_ERROR and
    does NOT re-raise the original across the public API.
    """
    from arc_guard_core.policy import (
        PolicyRule,
        PolicyRuleSet,
        RiskBand,
        RiskThresholds,
    )
    from arc_guard_core.types import Finding, RiskLevel

    class _StubInspector:
        async def inspect(self, result):  # type: ignore[no-untyped-def]
            from dataclasses import replace

            return replace(
                result,
                findings=(Finding("PII_EMAIL", 0, 5, RiskLevel.MEDIUM, "stub"),),
            )

    ruleset = PolicyRuleSet(
        rules=(PolicyRule(id="r1", match="PII_EMAIL", strategy="redact"),),
        risk_thresholds=RiskThresholds(),
        ambiguous_threshold=RiskBand.MEDIUM,
    )
    pipeline = GuardPipeline(
        inspectors=[_StubInspector()],
        policy_ruleset=ruleset,
        policy_router=_RaisingPolicyRouter(),  # raises _MyAppError
        tracer_hook=RecordingTracer(),
        logger_hook=RecordingLogger(),
        metrics_hook=RecordingMetricSink(),
    )

    # No exception propagates across the public API — that's the
    # foundation no-leak contract.
    result = await pipeline.pre_process(GuardInput(text="hello@example.com"))

    assert result.refusal is not None
    assert result.refusal.code == str(RefusalCode.INTERNAL_UNKNOWN_ERROR)
    assert result.refusal.trigger == "_MyAppError"
    assert result.action == "block"
