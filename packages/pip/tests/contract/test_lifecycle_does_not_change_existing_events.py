"""Contract: wiring a lifecycle sink does not change the events that the
existing RecordingLogger receives. Snapshots two runs over the same
input — one with a real lifecycle hook, one without — and asserts the
RecordingLogger's normalized capture is byte-identical.

Volatile fields (timestamps, run-fresh ids, durations) are stripped before
comparison so the assertion targets the SHAPE of the event stream
(name + level + non-volatile fields), not the timing of any single run.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from arc_guard_core.lifecycle import LifecycleEmitter, NullLifecycleSink
from arc_guard_core.types import GuardContext, GuardInput

from arc_guard.observability import RecordingLogger
from arc_guard.observability.ring_buffer_lifecycle_sink import RingBufferLifecycleSink
from arc_guard.pipeline import GuardPipeline

_VOLATILE_FIELDS = frozenset({
    "decision_id",
    "duration_ms",
    "total_duration_ms",
    "latency_ms",
    "elapsed_ms",
    "intent_size_bytes",
    "input_size_bytes",
    "span_id",
    "trace_id",
})


def _snapshot(logger: RecordingLogger) -> str:
    """Project logger captures into a deterministic JSON string."""
    rows: list[dict[str, Any]] = []
    for ev in logger.captured_events:
        clean_fields = {
            k: v for k, v in ev.fields.items() if k not in _VOLATILE_FIELDS
        }
        rows.append({
            "name": ev.name,
            "level": ev.level,
            "fields": clean_fields,
        })
    return json.dumps(rows, sort_keys=True, default=str)


@pytest.mark.asyncio
async def test_lifecycle_hook_does_not_change_logger_event_stream() -> None:
    text = "deterministic input for snapshot comparison"
    fixed_corr = "fixed-corr-snapshot"

    logger_baseline = RecordingLogger()
    pipeline_baseline = GuardPipeline(
        inspectors=[],
        logger_hook=logger_baseline,
    )
    await pipeline_baseline.pre_process(
        GuardInput(text=text, context=GuardContext(correlation_id=fixed_corr)),
    )
    await asyncio.sleep(0.05)

    logger_with_lifecycle = RecordingLogger()
    sink = RingBufferLifecycleSink(capacity=200)
    emitter = LifecycleEmitter(sink, "snapshot-rid")
    pipeline_with_lifecycle = GuardPipeline(
        inspectors=[],
        logger_hook=logger_with_lifecycle,
        lifecycle_hook=sink,
    )
    await pipeline_with_lifecycle.pre_process(
        GuardInput(
            text=text,
            context=GuardContext(
                correlation_id=fixed_corr,
                metadata={"_lifecycle_emitter": emitter, "_lifecycle_parent_id": None},
            ),
        )
    )
    await asyncio.sleep(0.05)

    baseline_snapshot = _snapshot(logger_baseline)
    with_lifecycle_snapshot = _snapshot(logger_with_lifecycle)

    assert baseline_snapshot == with_lifecycle_snapshot, (
        "Wiring a lifecycle sink changed the RecordingLogger's event stream.\n"
        f"baseline: {baseline_snapshot[:600]}\n"
        f"with_lifecycle: {with_lifecycle_snapshot[:600]}"
    )


@pytest.mark.asyncio
async def test_null_lifecycle_hook_matches_no_lifecycle_at_all() -> None:
    """Sanity guard: a NullLifecycleSink and the absence-of-hook path must
    both leave the logger stream identical."""
    text = "another deterministic input"
    fixed_corr = "fixed-corr-null-vs-absent"

    logger_absent = RecordingLogger()
    await GuardPipeline(inspectors=[], logger_hook=logger_absent).pre_process(
        GuardInput(text=text, context=GuardContext(correlation_id=fixed_corr)),
    )
    await asyncio.sleep(0.05)

    logger_null = RecordingLogger()
    await GuardPipeline(
        inspectors=[],
        logger_hook=logger_null,
        lifecycle_hook=NullLifecycleSink(),
    ).pre_process(
        GuardInput(text=text, context=GuardContext(correlation_id=fixed_corr)),
    )
    await asyncio.sleep(0.05)

    assert _snapshot(logger_absent) == _snapshot(logger_null)
