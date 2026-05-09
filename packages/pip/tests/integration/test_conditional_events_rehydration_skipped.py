"""Conditional event: RehydrationVerified is NOT emitted under the default
NullRehydrationVerifier. The rehydrate stage still runs (and may rewrite
text) but the lifecycle event only fires for a wired non-null verifier.
"""

from __future__ import annotations

import asyncio

import pytest
from arc_guard_core.lifecycle import LifecycleEmitter
from arc_guard_core.lifecycle.events import RehydrationVerified
from arc_guard_core.policy import PolicyRule, PolicyRuleSet
from arc_guard_core.types import Finding, GuardContext, GuardInput, GuardResult, RiskLevel

from arc_guard.observability.ring_buffer_lifecycle_sink import RingBufferLifecycleSink
from arc_guard.pipeline import GuardPipeline


class _StaticEmailInspector:
    name = "static_email"

    async def inspect(self, result: GuardResult) -> GuardResult:
        return GuardResult(
            text=result.text,
            action=result.action,
            findings=tuple(result.findings) + (
                Finding("EMAIL_ADDRESS", 12, 29, RiskLevel.HIGH, "static_email"),
            ),
            phase=result.phase,
        )


@pytest.mark.asyncio
async def test_default_null_verifier_does_not_emit_rehydration_verified() -> None:
    sink = RingBufferLifecycleSink(capacity=200)
    rid = "rehydrate-skipped"
    emitter = LifecycleEmitter(sink, rid)

    policy = PolicyRuleSet(
        rules=(PolicyRule(id="r_email", match="EMAIL_ADDRESS", strategy="redact"),),
    )
    pipeline = GuardPipeline(
        policy_ruleset=policy,
        inspectors=[_StaticEmailInspector()],
        lifecycle_hook=sink,
    )

    await pipeline.pre_process(
        GuardInput(
            text="my email is alice@example.com please",
            context=GuardContext(
                metadata={"_lifecycle_emitter": emitter, "_lifecycle_parent_id": None},
            ),
        )
    )
    await asyncio.sleep(0.05)

    events = await sink.query(rid)
    assert events is not None
    rv = [e for e in events if isinstance(e, RehydrationVerified)]
    assert rv == [], (
        f"RehydrationVerified must NOT fire under the default NullRehydrationVerifier; got {rv}"
    )
