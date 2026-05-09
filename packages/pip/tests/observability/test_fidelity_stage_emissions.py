"""Recording sinks capture STAGE_DEFEND + STAGE_VERIFY spans/events."""

from __future__ import annotations

import pytest
from arc_guard_core.fidelity import FidelityScore
from arc_guard_core.protocols.intent_encoder import (
    IntentEncoder,
    IntentRepresentation,
)
from arc_guard_core.types import GuardInput

from arc_guard.observability import (
    RecordingLogger,
    RecordingMetricSink,
    RecordingTracer,
)
from arc_guard.pipeline import GuardPipeline


class _StubEncoder:
    @property
    def encoder_id(self) -> str:
        return "stub-emit:1"

    def encode(self, text: str) -> IntentRepresentation:
        return text


class _StubScorer:
    def compatible_with(self, encoder: IntentEncoder) -> bool:
        return encoder.encoder_id.startswith("stub-emit:")

    def score(
        self,
        intent: IntentRepresentation,
        answer: IntentRepresentation,
    ) -> FidelityScore:
        return FidelityScore.measured(0.85)


@pytest.mark.asyncio
async def test_defend_stage_emits_span_and_event() -> None:
    tracer = RecordingTracer()
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()
    pipeline = GuardPipeline(
        inspectors=[],
        intent_encoder=_StubEncoder(),
        fidelity_scorer=_StubScorer(),
        tracer_hook=tracer,
        logger_hook=logger,
        metrics_hook=metric_sink,
    )

    await pipeline.pre_process(GuardInput(text="hello"))

    defend_spans = [s for s in tracer.captured_spans if s.attributes.get("stage") == "defend"]
    assert len(defend_spans) == 1

    intent_events = [e for e in logger.captured_events if e.name == "guard.intent.captured"]
    assert len(intent_events) == 1
    fields = intent_events[0].fields
    assert fields["encoder_id"] == "stub-emit:1"
    assert fields["intent_size_bytes"] == len(b"hello")


@pytest.mark.asyncio
async def test_verify_stage_emits_span_event_and_metrics() -> None:
    tracer = RecordingTracer()
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()
    pipeline = GuardPipeline(
        inspectors=[],
        intent_encoder=_StubEncoder(),
        fidelity_scorer=_StubScorer(),
        tracer_hook=tracer,
        logger_hook=logger,
        metrics_hook=metric_sink,
    )

    await pipeline.pre_process(GuardInput(text="hello"))

    verify_spans = [s for s in tracer.captured_spans if s.attributes.get("stage") == "verify"]
    assert len(verify_spans) == 1

    scored_events = [e for e in logger.captured_events if e.name == "guard.fidelity.scored"]
    assert len(scored_events) == 1
    fields = scored_events[0].fields
    assert fields["score_value"] == 0.85
    assert fields["score_sentinel"] == "measured"
    assert fields["band"] == "above_warn"

    score_counters = [
        m for m in metric_sink.captured_metrics
        if m.name == "arc_guardrails.fidelity.score"
    ]
    assert len(score_counters) == 1
    assert score_counters[0].attributes["band"] == "above_warn"
    assert score_counters[0].attributes["sentinel"] == "measured"

    duration_hists = [
        m for m in metric_sink.captured_metrics
        if m.name == "arc_guardrails.fidelity.duration"
    ]
    assert len(duration_hists) == 1


@pytest.mark.asyncio
async def test_null_defaults_emit_sentinel_in_band_attribute() -> None:
    tracer = RecordingTracer()
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()
    pipeline = GuardPipeline(
        inspectors=[],
        tracer_hook=tracer,
        logger_hook=logger,
        metrics_hook=metric_sink,
    )

    await pipeline.pre_process(GuardInput(text="hello"))

    scored_events = [e for e in logger.captured_events if e.name == "guard.fidelity.scored"]
    assert len(scored_events) == 1
    assert scored_events[0].fields["score_sentinel"] == "not_measured"
    assert scored_events[0].fields["band"] == "not_measured"
