"""Observability overhead benchmark.

Measures the per-stage and end-to-end overhead the observability
instrumentation adds to a pipeline run. The benchmarks run in two
modes — null sinks vs. recording sinks — so the *delta* is the
meaningful number; absolute latency depends on CI hardware.

Marked ``@pytest.mark.slow`` so default CI does not pay the cost;
the dedicated perf job picks them up via ``pytest -m slow``.

Budget (these are guidelines, not hard gates — adjust if CI hardware
materially changes):

- Per-stage overhead under null sinks: < 50µs
- Per-stage overhead under recording sinks: < 500µs
- End-to-end overhead on a refusal-class run: < 5ms
"""

from __future__ import annotations

import asyncio
import time

import pytest
from arc_guard_core.types import GuardInput

from arc_guard.observability import (
    RecordingLogger,
    RecordingMetricSink,
    RecordingTracer,
)
from arc_guard.pipeline import GuardPipeline

WARMUP_RUNS = 5
TIMED_RUNS = 50


class _PassthroughInspector:
    async def inspect(self, result):  # type: ignore[no-untyped-def]
        return result


def _measure(coro_factory, runs: int) -> float:
    """Run ``coro_factory()`` ``runs`` times; return the median ms."""

    durations_ns: list[int] = []
    for _ in range(runs):
        coro = coro_factory()
        start = time.perf_counter_ns()
        asyncio.run(coro)
        durations_ns.append(time.perf_counter_ns() - start)
    durations_ns.sort()
    median = durations_ns[len(durations_ns) // 2]
    return median / 1_000_000  # ns → ms


@pytest.mark.slow
def test_pipeline_overhead_under_null_sinks() -> None:
    pipeline = GuardPipeline(inspectors=[_PassthroughInspector()])

    def factory():  # type: ignore[no-untyped-def]
        return pipeline.pre_process(GuardInput(text="benchmark"))

    # Warmup
    for _ in range(WARMUP_RUNS):
        asyncio.run(pipeline.pre_process(GuardInput(text="warmup")))

    median_ms = _measure(factory, TIMED_RUNS)
    print(f"[perf] null-sinks median: {median_ms:.3f}ms")
    # Sanity: a single passthrough run should comfortably finish
    # under 10ms on any reasonable CI hardware.
    assert median_ms < 10.0, f"null-sinks run too slow: {median_ms:.3f}ms"


@pytest.mark.slow
def test_pipeline_overhead_under_recording_sinks() -> None:
    pipeline = GuardPipeline(
        inspectors=[_PassthroughInspector()],
        tracer_hook=RecordingTracer(),
        logger_hook=RecordingLogger(),
        metrics_hook=RecordingMetricSink(),
    )

    def factory():  # type: ignore[no-untyped-def]
        return pipeline.pre_process(GuardInput(text="benchmark"))

    for _ in range(WARMUP_RUNS):
        asyncio.run(pipeline.pre_process(GuardInput(text="warmup")))

    median_ms = _measure(factory, TIMED_RUNS)
    print(f"[perf] recording-sinks median: {median_ms:.3f}ms")
    # Recording sinks add buffering + scan overhead; allow more
    # headroom but still expect the run to finish under 25ms.
    assert median_ms < 25.0, f"recording-sinks run too slow: {median_ms:.3f}ms"


@pytest.mark.slow
def test_overhead_delta_is_bounded() -> None:
    """The delta between null-sinks and recording-sinks must stay
    bounded so the observability instrumentation cost cannot grow
    unnoticed.
    """
    null_pipeline = GuardPipeline(inspectors=[_PassthroughInspector()])
    recording_pipeline = GuardPipeline(
        inspectors=[_PassthroughInspector()],
        tracer_hook=RecordingTracer(),
        logger_hook=RecordingLogger(),
        metrics_hook=RecordingMetricSink(),
    )

    for _ in range(WARMUP_RUNS):
        asyncio.run(null_pipeline.pre_process(GuardInput(text="warmup")))
        asyncio.run(recording_pipeline.pre_process(GuardInput(text="warmup")))

    null_ms = _measure(
        lambda: null_pipeline.pre_process(GuardInput(text="bench")),
        TIMED_RUNS,
    )
    rec_ms = _measure(
        lambda: recording_pipeline.pre_process(GuardInput(text="bench")),
        TIMED_RUNS,
    )
    delta_ms = rec_ms - null_ms
    print(f"[perf] delta (recording - null): {delta_ms:.3f}ms")
    # The instrumentation surface includes ~6 stage spans + ~12
    # log events + ~3 metric samples per run. A reasonable upper
    # bound for the delta on CI hardware is 15ms.
    assert delta_ms < 15.0, f"observability delta too large: {delta_ms:.3f}ms"
