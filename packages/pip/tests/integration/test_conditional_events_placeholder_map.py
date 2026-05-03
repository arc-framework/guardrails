"""Conditional event: PlaceholderMapBuilt request-level summary.

Without raw capture, the event carries the placeholder count + entity types
but `map` is None. With raw capture enabled, `map` carries the per-placeholder
raw substring (security-sensitive).
"""

from __future__ import annotations

import asyncio

import pytest
from arc_guard_core.lifecycle import LifecycleEmitter
from arc_guard_core.lifecycle.events import PlaceholderMapBuilt
from arc_guard_core.types import Finding, GuardContext, GuardInput, GuardResult, RiskLevel

from arc_guard.observability.ring_buffer_lifecycle_sink import RingBufferLifecycleSink
from arc_guard.pipeline import GuardPipeline


class _StaticEmailInspector:
    name = "static_email"

    def __init__(self, span: tuple[int, int]) -> None:
        self._span = span

    async def inspect(self, result: GuardResult) -> GuardResult:
        s, e = self._span
        return GuardResult(
            text=result.text,
            action=result.action,
            findings=tuple(result.findings) + (
                Finding("EMAIL_ADDRESS", s, e, RiskLevel.LOW, "static_email"),
            ),
            phase=result.phase,
        )


class _RawCapturePolicy:
    def should_capture_sanitized(self) -> bool:
        return False

    def should_capture_raw_input(self) -> bool:
        return True


def _build_pipeline(sink: RingBufferLifecycleSink) -> GuardPipeline:
    return GuardPipeline(
        inspectors=[_StaticEmailInspector(span=(12, 29))],
        lifecycle_hook=sink,
    )


PII_TEXT = "my email is alice@example.com please"


@pytest.mark.asyncio
async def test_placeholder_map_event_default_policy_has_no_map() -> None:
    sink = RingBufferLifecycleSink(capacity=200)
    rid = "ph-map-default"
    emitter = LifecycleEmitter(sink, rid)
    pipeline = _build_pipeline(sink)

    await pipeline.pre_process(
        GuardInput(
            text=PII_TEXT,
            context=GuardContext(
                metadata={"_lifecycle_emitter": emitter, "_lifecycle_parent_id": None},
            ),
        )
    )
    await asyncio.sleep(0.05)

    events = await sink.query(rid)
    assert events is not None
    pmb = [e for e in events if isinstance(e, PlaceholderMapBuilt)]
    assert len(pmb) == 1, f"expected exactly one PlaceholderMapBuilt, got {len(pmb)}"
    ev = pmb[0]
    assert ev.placeholder_count == 1
    assert ev.entity_types == ["EMAIL_ADDRESS"]
    assert ev.map is None, "map MUST be None under default (no-raw-capture) policy"


@pytest.mark.asyncio
async def test_placeholder_map_event_raw_capture_populates_map() -> None:
    sink = RingBufferLifecycleSink(capacity=200)
    rid = "ph-map-raw"
    emitter = LifecycleEmitter(sink, rid, policy=_RawCapturePolicy())
    pipeline = _build_pipeline(sink)

    await pipeline.pre_process(
        GuardInput(
            text=PII_TEXT,
            context=GuardContext(
                metadata={"_lifecycle_emitter": emitter, "_lifecycle_parent_id": None},
            ),
        )
    )
    await asyncio.sleep(0.05)

    events = await sink.query(rid)
    assert events is not None
    pmb = [e for e in events if isinstance(e, PlaceholderMapBuilt)]
    assert len(pmb) == 1
    ev = pmb[0]
    assert ev.placeholder_count == 1
    assert ev.entity_types == ["EMAIL_ADDRESS"]
    assert ev.map is not None and ev.map.get("[EMAIL_ADDRESS]") == "alice@example.com"
