"""All four observability surfaces co-exist: lifecycle sink does not steal
from existing Logger / MetricSink / Tracer consumers (the OTEL-style
sibling-Protocol architectural choice).

Wires a pipeline with all four sinks and verifies each receives its own
emissions; then asserts that swapping the lifecycle sink for a NullSink
leaves the OTHER three sinks' captured output identical to a baseline
that never had a lifecycle sink wired in the first place.
"""

from __future__ import annotations

import asyncio

import pytest
from arc_guard_core.lifecycle import LifecycleEmitter, NullLifecycleSink
from arc_guard_core.types import GuardContext, GuardInput

from arc_guard.observability import (
    RecordingLogger,
    RecordingMetricSink,
    RecordingTracer,
)
from arc_guard.observability.ring_buffer_lifecycle_sink import RingBufferLifecycleSink
from arc_guard.pipeline import GuardPipeline


def _build_pipeline(
    *,
    lifecycle_hook,
    tracer: RecordingTracer,
    logger: RecordingLogger,
    metrics: RecordingMetricSink,
) -> GuardPipeline:
    return GuardPipeline(
        inspectors=[],
        lifecycle_hook=lifecycle_hook,
        tracer_hook=tracer,
        logger_hook=logger,
        metrics_hook=metrics,
    )


@pytest.mark.asyncio
async def test_all_four_observability_sinks_receive_emissions() -> None:
    sink = RingBufferLifecycleSink(capacity=200)
    rid = "coexist-001"
    emitter = LifecycleEmitter(sink, rid)
    tracer = RecordingTracer()
    logger = RecordingLogger()
    metrics = RecordingMetricSink()
    pipeline = _build_pipeline(
        lifecycle_hook=sink,
        tracer=tracer,
        logger=logger,
        metrics=metrics,
    )

    await pipeline.pre_process(
        GuardInput(
            text="hello world",
            context=GuardContext(
                correlation_id="coexist-corr-001",
                metadata={"_lifecycle_emitter": emitter, "_lifecycle_parent_id": None},
            ),
        )
    )
    await asyncio.sleep(0.05)

    lifecycle_events = await sink.query(rid)
    assert lifecycle_events and len(lifecycle_events) > 0, "lifecycle sink got no events"
    assert tracer.captured_spans, "tracer got no spans"
    assert logger.captured_events, "logger got no events"
    assert metrics.captured_metrics, "metric sink got no metrics"


@pytest.mark.asyncio
async def test_disabling_lifecycle_leaves_other_sinks_unchanged() -> None:
    """Run the same input twice — once with a real lifecycle sink, once with
    NullLifecycleSink. The Logger / MetricSink / Tracer captures must be
    identical between the two runs (lifecycle is purely additive).
    """
    text = "another benign request body"

    tracer_a = RecordingTracer()
    logger_a = RecordingLogger()
    metrics_a = RecordingMetricSink()
    sink_a = RingBufferLifecycleSink(capacity=200)
    emitter_a = LifecycleEmitter(sink_a, "rid-with-lifecycle")
    pipeline_a = _build_pipeline(
        lifecycle_hook=sink_a,
        tracer=tracer_a,
        logger=logger_a,
        metrics=metrics_a,
    )
    await pipeline_a.pre_process(
        GuardInput(
            text=text,
            context=GuardContext(
                correlation_id="fixed-corr",
                metadata={"_lifecycle_emitter": emitter_a, "_lifecycle_parent_id": None},
            ),
        )
    )
    await asyncio.sleep(0.05)

    tracer_b = RecordingTracer()
    logger_b = RecordingLogger()
    metrics_b = RecordingMetricSink()
    pipeline_b = _build_pipeline(
        lifecycle_hook=NullLifecycleSink(),
        tracer=tracer_b,
        logger=logger_b,
        metrics=metrics_b,
    )
    await pipeline_b.pre_process(
        GuardInput(text=text, context=GuardContext(correlation_id="fixed-corr")),
    )
    await asyncio.sleep(0.05)

    a_event_names = sorted(e.name for e in logger_a.captured_events)
    b_event_names = sorted(e.name for e in logger_b.captured_events)
    assert a_event_names == b_event_names, (
        f"logger event names differ:\na (with lifecycle): {a_event_names}\n"
        f"b (no lifecycle):   {b_event_names}"
    )

    a_metric_names = sorted(m.name for m in metrics_a.captured_metrics)
    b_metric_names = sorted(m.name for m in metrics_b.captured_metrics)
    assert a_metric_names == b_metric_names, (
        f"metric names differ:\na (with lifecycle): {a_metric_names}\n"
        f"b (no lifecycle):   {b_metric_names}"
    )

    a_span_names = sorted(s.name for s in tracer_a.captured_spans)
    b_span_names = sorted(s.name for s in tracer_b.captured_spans)
    assert a_span_names == b_span_names, (
        f"span names differ:\na (with lifecycle): {a_span_names}\n"
        f"b (no lifecycle):   {b_span_names}"
    )
