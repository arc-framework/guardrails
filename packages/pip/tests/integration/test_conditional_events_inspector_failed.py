"""Conditional event: InspectorFailed fires when an inspector raises; pipeline fail-opens."""

from __future__ import annotations

import asyncio

import pytest
from arc_guard_core.lifecycle import LifecycleEmitter
from arc_guard_core.lifecycle.events import InspectorFailed
from arc_guard_core.types import GuardContext, GuardInput, GuardResult

from arc_guard.observability.ring_buffer_lifecycle_sink import RingBufferLifecycleSink
from arc_guard.pipeline import GuardPipeline


class _AlwaysRaisingInspector:
    name = "always_raises"

    async def inspect(self, result: GuardResult) -> GuardResult:
        raise RuntimeError("intentional inspector failure for test")


@pytest.mark.asyncio
async def test_inspector_exception_emits_inspector_failed_event_and_fail_opens() -> None:
    sink = RingBufferLifecycleSink(capacity=200)
    rid = "inspector-failed-001"
    emitter = LifecycleEmitter(sink, rid)

    pipeline = GuardPipeline(
        inspectors=[_AlwaysRaisingInspector()],
        lifecycle_hook=sink,
    )

    result = await pipeline.pre_process(
        GuardInput(
            text="something benign",
            context=GuardContext(
                metadata={"_lifecycle_emitter": emitter, "_lifecycle_parent_id": None},
            ),
        )
    )
    await asyncio.sleep(0.05)

    assert result is not None

    events = await sink.query(rid)
    assert events is not None
    failed = [e for e in events if isinstance(e, InspectorFailed)]
    assert len(failed) == 1, f"expected exactly one InspectorFailed event, got {len(failed)}"
    ev = failed[0]
    assert ev.inspector_name == "_AlwaysRaisingInspector"
    assert ev.exception_class == "RuntimeError"
    assert ev.traceback_id.startswith("tb_")
