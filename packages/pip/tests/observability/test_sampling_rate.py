"""Sampling rate produces a statistically observable export rate.

Runs a 200-input workload at ``sampling_rate=0.1`` and asserts the
share of exported runs falls in a binomial 99% confidence interval
around the configured rate. This is a probabilistic test — it can
flake under hostile RNG luck — so we use a wide enough interval
that flake is structurally rare (the 99% CI for a 200-trial Bernoulli
at p=0.1 spans roughly [0.05, 0.16]).
"""

from __future__ import annotations

import pytest
from arc_guard_core.config import GuardConfig
from arc_guard_core.observability_config import ObservabilityConfig
from arc_guard_core.types import GuardInput

from arc_guard.observability import (
    RecordingLogger,
    RecordingMetricSink,
    RecordingTracer,
)
from arc_guard.pipeline import GuardPipeline

WORKLOAD_SIZE = 200
SAMPLING_RATE = 0.1
# 99% CI for B(200, 0.1) ≈ [0.05, 0.16]; we accept anything in that
# range. A miss this wide indicates a real problem, not bad luck.
ACCEPTABLE_MIN = 0.05
ACCEPTABLE_MAX = 0.16


@pytest.mark.asyncio
async def test_sampling_rate_matches_configured_within_tolerance() -> None:
    config = GuardConfig(
        observability=ObservabilityConfig(
            sampling_rate=SAMPLING_RATE,
            refusal_always_emits=False,  # disable the refusal override
        ),
    )
    tracer = RecordingTracer()
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()
    pipeline = GuardPipeline(
        config=config,
        inspectors=[],
        tracer_hook=tracer,
        logger_hook=logger,
        metrics_hook=metric_sink,
    )

    # Run the workload. Each run produces one ``guard.run.completed``
    # event when sampled in; sampled-out runs drop the buffered events.
    for i in range(WORKLOAD_SIZE):
        await pipeline.pre_process(GuardInput(text=f"sample-test-{i}"))

    completed_events = [e for e in logger.captured_events if e.name == "guard.run.completed"]
    observed_rate = len(completed_events) / WORKLOAD_SIZE
    assert ACCEPTABLE_MIN <= observed_rate <= ACCEPTABLE_MAX, (
        f"observed sampling rate {observed_rate:.3f} outside "
        f"[{ACCEPTABLE_MIN}, {ACCEPTABLE_MAX}] for configured "
        f"sampling_rate={SAMPLING_RATE} on {WORKLOAD_SIZE} runs"
    )


@pytest.mark.asyncio
async def test_sampling_rate_one_emits_every_run() -> None:
    config = GuardConfig(
        observability=ObservabilityConfig(sampling_rate=1.0),
    )
    tracer = RecordingTracer()
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()
    pipeline = GuardPipeline(
        config=config,
        inspectors=[],
        tracer_hook=tracer,
        logger_hook=logger,
        metrics_hook=metric_sink,
    )

    for i in range(20):
        await pipeline.pre_process(GuardInput(text=f"full-sample-{i}"))

    completed_events = [e for e in logger.captured_events if e.name == "guard.run.completed"]
    assert len(completed_events) == 20


@pytest.mark.asyncio
async def test_sampling_rate_zero_drops_all_non_refusal_runs() -> None:
    config = GuardConfig(
        observability=ObservabilityConfig(
            sampling_rate=0.0,
            refusal_always_emits=False,
        ),
    )
    tracer = RecordingTracer()
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()
    pipeline = GuardPipeline(
        config=config,
        inspectors=[],
        tracer_hook=tracer,
        logger_hook=logger,
        metrics_hook=metric_sink,
    )

    for i in range(20):
        await pipeline.pre_process(GuardInput(text=f"zero-sample-{i}"))

    completed_events = [e for e in logger.captured_events if e.name == "guard.run.completed"]
    assert len(completed_events) == 0
    # Metrics still emit unconditionally — the run.action counter
    # fires for every run regardless of sampling.
    action_metrics = [
        m for m in metric_sink.captured_metrics if m.name == "arc_guardrails.run.action"
    ]
    assert len(action_metrics) == 20
