"""Async stress test: 100 concurrent coroutines + event-loop canary.

Drives a single ``GuardPipeline`` through ``asyncio.gather`` with 100
distinct inputs while a separate canary coroutine schedules a 1ms
sleep every 10ms during the run. Asserts every result corresponds to
its own input and the canary's p99 scheduling jitter stays under
10ms — proving the pipeline does not block the event loop beyond the
documented budget.

This test exercises both the no-cross-talk and event-loop-blocking
properties — split across two assertions in the same test so a
regression in either dimension is caught against the same workload.
"""

from __future__ import annotations

import asyncio
import statistics
import time
import uuid

import pytest
from arc_guard_core.types import GuardContext, GuardInput

from arc_guard.observability import (
    RecordingLogger,
    RecordingMetricSink,
    RecordingTracer,
)
from arc_guard.pipeline import GuardPipeline

CONCURRENT_REQUESTS = 100
CANARY_TICK_S = 0.001  # tick every 1ms — high-resolution scheduling probe
MAX_P99_JITTER_MS = 10.0


class _AsyncPassthroughInspector:
    async def inspect(self, result):  # type: ignore[no-untyped-def]
        return result


async def _canary_jitter_samples(stop_event: asyncio.Event) -> list[float]:
    """Tick every 1ms; record how late each tick actually fired.

    Jitter is the gap between the requested 1ms tick interval and the
    observed gap. On a healthy event loop the gap stays close to 1ms;
    a blocked loop produces gaps of tens of ms.
    """
    samples_ms: list[float] = []
    last = time.monotonic()
    while not stop_event.is_set():
        await asyncio.sleep(CANARY_TICK_S)
        observed = time.monotonic()
        elapsed_ms = (observed - last) * 1000.0
        target_ms = CANARY_TICK_S * 1000.0
        samples_ms.append(abs(elapsed_ms - target_ms))
        last = observed
    return samples_ms


@pytest.mark.asyncio
async def test_asyncio_stress_no_cross_talk_and_event_loop_stays_responsive() -> None:
    pipeline = GuardPipeline(
        inspectors=[_AsyncPassthroughInspector()],
        tracer_hook=RecordingTracer(),
        logger_hook=RecordingLogger(),
        metrics_hook=RecordingMetricSink(),
    )
    markers = [uuid.uuid4().hex for _ in range(CONCURRENT_REQUESTS)]

    stop_event = asyncio.Event()
    canary_task = asyncio.create_task(_canary_jitter_samples(stop_event))

    async def run_one(marker: str) -> tuple[str, str]:
        text = f"input-marker:{marker}"
        result = await pipeline.pre_process(
            GuardInput(text=text, context=GuardContext(correlation_id=marker)),
        )
        return marker, result.text

    try:
        outcomes = await asyncio.gather(*(run_one(m) for m in markers))
    finally:
        stop_event.set()
        samples_ms = await canary_task

    # No cross-talk
    for marker, text in outcomes:
        assert marker in text, f"cross-talk: marker {marker!r} missing from result {text!r}"

    # Event-loop canary: p99 jitter under the documented threshold.
    assert samples_ms, "canary collected no samples"
    samples_sorted = sorted(samples_ms)
    p99_index = max(0, int(len(samples_sorted) * 0.99) - 1)
    p99_jitter_ms = samples_sorted[p99_index]
    assert p99_jitter_ms < MAX_P99_JITTER_MS, (
        f"event-loop p99 jitter {p99_jitter_ms:.2f}ms exceeds "
        f"{MAX_P99_JITTER_MS}ms budget; mean={statistics.mean(samples_ms):.2f}ms"
    )
