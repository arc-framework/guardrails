"""Conditional event: RehydrationVerified is NOT emitted under the default
NullRehydrationVerifier. The rehydrate stage still runs (and may rewrite
text) but the lifecycle event only fires for a wired non-null verifier.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping

import pytest
from arc_guard_core.lifecycle import LifecycleEmitter
from arc_guard_core.lifecycle.events import RehydrationVerified
from arc_guard_core.policy import PolicyRule, PolicyRuleSet
from arc_guard_core.protocols.rehydration_verifier import RehydrationVerdict
from arc_guard_core.types import Finding, GuardContext, GuardInput, GuardResult, RiskLevel

from arc_guard.observability.ring_buffer_lifecycle_sink import RingBufferLifecycleSink
from arc_guard.pipeline import GuardPipeline


class _StaticEmailInspector:
    name = "static_email"

    def __init__(self, risk_level: RiskLevel = RiskLevel.HIGH) -> None:
        self._risk_level = risk_level

    async def inspect(self, result: GuardResult) -> GuardResult:
        return GuardResult(
            text=result.text,
            action=result.action,
            findings=tuple(result.findings)
            + (Finding("EMAIL_ADDRESS", 12, 29, self._risk_level, "static_email"),),
            phase=result.phase,
        )


class _CapturePolicy:
    def should_capture_sanitized(self) -> bool:
        return True

    def should_capture_raw_input(self) -> bool:
        return False


class _AcceptingVerifier:
    def verify(
        self,
        *,
        sanitized_prompt: str,
        rehydration_candidate: str,
        entity_map: Mapping[str, str],
    ) -> RehydrationVerdict:
        assert sanitized_prompt
        assert rehydration_candidate
        assert entity_map
        return RehydrationVerdict(decision="accept", reason="all_checks_passed")


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


@pytest.mark.asyncio
async def test_non_null_verifier_emits_rehydration_verified_with_capture_fields() -> None:
    sink = RingBufferLifecycleSink(capacity=200)
    rid = "rehydrate-emitted"
    emitter = LifecycleEmitter(sink, rid, policy=_CapturePolicy())

    # Adjusted to use a non-refusal risk band (MEDIUM instead of HIGH)
    policy = PolicyRuleSet(
        rules=(PolicyRule(id="r_email", match="EMAIL_ADDRESS", strategy="redact"),),
    )
    pipeline = GuardPipeline(
        policy_ruleset=policy,
        inspectors=[_StaticEmailInspector(RiskLevel.MEDIUM)],
        rehydration_verifier=_AcceptingVerifier(),
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
    assert len(rv) == 1, f"expected one RehydrationVerified event; got {rv!r}"
    assert rv[0].verifier_id == "_AcceptingVerifier"
    assert rv[0].outcome == "verified"
    assert rv[0].text_before is not None
    assert rv[0].text_after is not None
    assert "[EMAIL_ADDRESS" in rv[0].text_before
    assert "alice@example.com" in rv[0].text_after
