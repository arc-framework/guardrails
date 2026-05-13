"""Contract: the new optional text fields respect the capture flags.

The capture-gate matrix (per ``contracts/event-additions.md``) — when both
flags are off, no text fields populate; when ``capture_payloads=true``,
the post-sanitization text fields populate. The ``capture_raw_input``
flag is orthogonal; it controls only ``RequestStarted.raw_input`` and
the raw placeholder→original ``PlaceholderMapBuilt.map``.

This test pins the StrategyExecuted + SanitizationApplied gating because
those two are the most user-visible (the dashboard's Diff/Replay tab
renders them).
"""

from __future__ import annotations

import asyncio

import pytest
from arc_guard_core.lifecycle import LifecycleEmitter
from arc_guard_core.lifecycle.events import (
    SanitizationApplied,
    StrategyExecuted,
)
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

    async def inspect(self, result: GuardResult) -> GuardResult:
        return GuardResult(
            text=result.text,
            action=result.action,
            findings=tuple(result.findings)
            + (Finding("EMAIL_ADDRESS", 0, 19, RiskLevel.MEDIUM, "stub"),),
            phase=result.phase,
        )


class _Policy:
    """Hand-rolled PayloadCapturePolicy for parametrized testing."""

    def __init__(self, *, sanitized: bool, raw_input: bool) -> None:
        self._sanitized = sanitized
        self._raw_input = raw_input

    def should_capture_sanitized(self) -> bool:
        return self._sanitized

    def should_capture_raw_input(self) -> bool:
        return self._raw_input


async def _run_redact(policy: _Policy) -> tuple[StrategyExecuted, SanitizationApplied]:
    sink = RingBufferLifecycleSink(capacity=200)
    rid = f"capture-rid-{policy._sanitized}-{policy._raw_input}"
    emitter = LifecycleEmitter(sink, rid, policy=policy)

    pipeline = GuardPipeline(
        policy_ruleset=PolicyRuleSet(
            rules=(PolicyRule(id="r_email", match="EMAIL_ADDRESS", strategy="redact"),),
        ),
        inspectors=[_StubInspector()],
        lifecycle_hook=sink,
    )
    await pipeline.pre_process(
        GuardInput(
            text="alice@example.com please",
            context=GuardContext(
                metadata={"_lifecycle_emitter": emitter, "_lifecycle_parent_id": None},
            ),
        )
    )
    await asyncio.sleep(0.05)

    events = await sink.query(rid)
    assert events is not None
    se = next((e for e in events if isinstance(e, StrategyExecuted)), None)
    sa = next((e for e in events if isinstance(e, SanitizationApplied)), None)
    assert se is not None, f"no StrategyExecuted in {events!r}"
    assert sa is not None, f"no SanitizationApplied in {events!r}"
    return se, sa


@pytest.mark.asyncio
async def test_capture_off_strategy_executed_text_fields_are_none() -> None:
    se, _ = await _run_redact(_Policy(sanitized=False, raw_input=False))
    assert se.text_before is None
    assert se.text_after is None


@pytest.mark.asyncio
async def test_capture_on_strategy_executed_text_fields_populate() -> None:
    se, _ = await _run_redact(_Policy(sanitized=True, raw_input=False))
    assert se.text_before is not None
    assert se.text_after is not None


@pytest.mark.asyncio
async def test_capture_off_sanitization_applied_text_fields_are_none() -> None:
    _, sa = await _run_redact(_Policy(sanitized=False, raw_input=False))
    assert sa.text_before is None
    assert sa.text_after is None


@pytest.mark.asyncio
async def test_capture_on_sanitization_applied_text_fields_populate() -> None:
    _, sa = await _run_redact(_Policy(sanitized=True, raw_input=False))
    assert sa.text_before is not None
    assert sa.text_after is not None


@pytest.mark.asyncio
async def test_raw_input_flag_does_not_affect_sanitized_text_fields() -> None:
    """capture_raw_input controls a different field — sanitized capture
    must remain off when only the raw flag is on."""
    se, sa = await _run_redact(_Policy(sanitized=False, raw_input=True))
    assert se.text_before is None
    assert se.text_after is None
    assert sa.text_before is None
    assert sa.text_after is None
