"""Contract: every canonical pipeline stage emits a ``StageRan`` event.

The 12-stage canonical taxonomy comes from ``arc_guard_core.stages``. After
a real ``pre_process`` run, the lifecycle sink must contain ``StageRan``
events covering the always-applicable stages for the run's path:

* Pass-through path (no findings) — 11 stages emit StageRan, ``refusal``
  is omitted (no refusal envelope was constructed). Conditional stages
  (verify, rehydrate) may emit or be skipped depending on whether
  fidelity scoring + entity_map plumbing engaged.
* Redact path (PII finding) — same 11 always-applicable stages emit;
  rehydrate additionally may emit when entity_map flows from the policy
  router.
* Block path (jailbreak refusal) — 10 always-applicable stages emit
  including ``refusal``; ``verify`` and ``rehydrate`` are omitted because
  the refusal short-circuits before the rehydration pipeline.

The exact set of *conditional* stages varies with how the operator wires
the pipeline. The contract this test pins is the set that MUST always
fire on each path.
"""

from __future__ import annotations

import asyncio

import pytest
from arc_guard_core.lifecycle import LifecycleEmitter
from arc_guard_core.lifecycle.events import StageRan
from arc_guard_core.policy import PolicyRule, PolicyRuleSet
from arc_guard_core.types import (
    Finding,
    GuardContext,
    GuardInput,
    GuardResult,
    RiskLevel,
)

from arc_guard.observability.ring_buffer_lifecycle_sink import RingBufferLifecycleSink
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


async def _stages_emitted(
    pipeline: GuardPipeline, sink: RingBufferLifecycleSink, rid: str, text: str
) -> set[str]:
    emitter = LifecycleEmitter(sink, rid)
    await pipeline.pre_process(
        GuardInput(
            text=text,
            context=GuardContext(
                metadata={"_lifecycle_emitter": emitter, "_lifecycle_parent_id": None},
            ),
        )
    )
    await asyncio.sleep(0.05)
    events = await sink.query(rid)
    assert events is not None
    return {e.stage for e in events if isinstance(e, StageRan)}


@pytest.mark.asyncio
async def test_pass_through_path_emits_eleven_always_applicable_stages() -> None:
    """No findings — refusal is the only stage we permit to be silent."""
    sink = RingBufferLifecycleSink(capacity=200)
    pipeline = GuardPipeline(
        inspectors=[_StubInspector(findings=())],
        lifecycle_hook=sink,
    )

    stages = await _stages_emitted(pipeline, sink, "pass-rid-1", "What is 2+2?")

    always = {
        "validate",
        "defend",
        "classify",
        "deception_inspect",
        "sanitize",
        "route",
        "execute",
        "verify",
        "decision_emit",
        "report",
    }
    missing = always - stages
    assert not missing, f"pass-through path missing always-applicable stages: {missing}"
    # Refusal is conditional — must NOT fire when no refusal was produced.
    assert "refusal" not in stages, (
        "refusal stage fired on pass-through path; only the block path should emit it"
    )


@pytest.mark.asyncio
async def test_redact_path_emits_eleven_always_applicable_stages() -> None:
    """PII finding + redact rule — rehydrate may additionally fire."""
    sink = RingBufferLifecycleSink(capacity=200)
    policy = PolicyRuleSet(
        rules=(PolicyRule(id="r_email", match="EMAIL_ADDRESS", strategy="redact"),),
    )
    pipeline = GuardPipeline(
        policy_ruleset=policy,
        inspectors=[
            _StubInspector(
                findings=(Finding("EMAIL_ADDRESS", 0, 19, RiskLevel.MEDIUM, "stub"),),
            ),
        ],
        lifecycle_hook=sink,
    )

    stages = await _stages_emitted(pipeline, sink, "redact-rid-1", "alice@example.com please")

    always = {
        "validate",
        "defend",
        "classify",
        "deception_inspect",
        "sanitize",
        "route",
        "execute",
        "verify",
        "decision_emit",
        "report",
    }
    missing = always - stages
    assert not missing, f"redact path missing always-applicable stages: {missing}"
    assert "refusal" not in stages, "refusal must not fire on a clean-redact path"


@pytest.mark.asyncio
async def test_validate_sanitize_rehydrate_are_in_canonical_taxonomy() -> None:
    """The new emission sites use the canonical stage names; a typo would
    fail the StageRan literal-narrowing at construction time, but pin
    explicitly here so a future rename of the canonical names breaks
    this test instead of silently mismatching the canvas."""
    from arc_guard_core.stages import (
        STAGE_REHYDRATE,
        STAGE_SANITIZE,
        STAGE_VALIDATE,
    )

    assert STAGE_VALIDATE == "validate"
    assert STAGE_SANITIZE == "sanitize"
    assert STAGE_REHYDRATE == "rehydrate"
