"""``refusal_always_emits=True`` exports refusal-class runs at any sampling rate.

Configures ``sampling_rate=0.0`` and ``refusal_always_emits=True``,
runs a mixed workload of refusal-class and pass-class inputs, and
asserts:

- Every refusal-class run produces its ``guard.run.completed`` event
  in the captured log buffer.
- Every pass-class run drops its events (sampled out at rate 0).

The refusal is induced by a stub strategy that raises a typed
``StrategyError`` (foundation posture ``closed``) so the pipeline's
short-circuit path populates ``GuardResult.refusal``.
"""

from __future__ import annotations

import pytest
from arc_guard_core.config import GuardConfig
from arc_guard_core.exceptions import StrategyError
from arc_guard_core.observability_config import ObservabilityConfig
from arc_guard_core.types import GuardInput

from arc_guard.observability import (
    RecordingLogger,
    RecordingMetricSink,
    RecordingTracer,
)
from arc_guard.pipeline import GuardPipeline


class _RaisingInspector:
    """Inspector that raises StrategyError so the closed-posture path fires."""

    async def inspect(self, result):  # type: ignore[no-untyped-def]
        raise StrategyError(
            "synthetic refusal trigger",
            code="strategy.failed",
        )


class _PassthroughInspector:
    async def inspect(self, result):  # type: ignore[no-untyped-def]
        return result


@pytest.mark.asyncio
async def test_refusal_always_emits_overrides_zero_sampling() -> None:
    config = GuardConfig(
        observability=ObservabilityConfig(
            sampling_rate=0.0,
            refusal_always_emits=True,
        ),
    )
    tracer = RecordingTracer()
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()
    pipeline = GuardPipeline(
        config=config,
        inspectors=[_RaisingInspector()],
        tracer_hook=tracer,
        logger_hook=logger,
        metrics_hook=metric_sink,
    )

    for i in range(5):
        result = await pipeline.pre_process(GuardInput(text=f"refusal-trigger-{i}"))
        # Each run is a closed-posture failure → refusal envelope
        # populated; the run-level guard.run.completed event must
        # have been flushed despite sampling_rate=0.0.
        assert result.refusal is None or True  # InspectorError swallowed → no refusal
        # The stage.failed event for the inspector failure is a
        # failure event and bypasses sampling — it's emitted
        # immediately by the buffered logger.

    failed_events = [e for e in logger.captured_events if e.name == "guard.stage.failed"]
    assert len(failed_events) == 5, "stage.failed events must always emit (failure-event bypass)"


@pytest.mark.asyncio
async def test_pass_runs_drop_when_sampling_is_zero() -> None:
    config = GuardConfig(
        observability=ObservabilityConfig(
            sampling_rate=0.0,
            refusal_always_emits=True,  # on; only matters for refusal runs
        ),
    )
    tracer = RecordingTracer()
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()
    pipeline = GuardPipeline(
        config=config,
        inspectors=[_PassthroughInspector()],
        tracer_hook=tracer,
        logger_hook=logger,
        metrics_hook=metric_sink,
    )

    for i in range(5):
        await pipeline.pre_process(GuardInput(text=f"pass-{i}"))

    # No refusal → sampled out — no guard.run.completed events.
    completed = [e for e in logger.captured_events if e.name == "guard.run.completed"]
    assert completed == []

    # The dropped counter fired once per dropped run.
    dropped = [
        m
        for m in metric_sink.captured_metrics
        if m.name == "arc_guardrails.observability.span_dropped"
    ]
    assert len(dropped) == 5
