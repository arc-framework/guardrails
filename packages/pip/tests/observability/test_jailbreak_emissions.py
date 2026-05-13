"""Recording sinks capture ``guard.jailbreak.detected`` events + counters."""

from __future__ import annotations

import pytest
from arc_guard_core.deception import ConversationState
from arc_guard_core.jailbreak import JailbreakSignal
from arc_guard_core.types import GuardInput

from arc_guard.observability import (
    RecordingLogger,
    RecordingMetricSink,
    RecordingTracer,
)
from arc_guard.pipeline import GuardPipeline


class _StubDetector:
    @property
    def detector_id(self) -> str:
        return "stub-emit:1"

    def detect(
        self,
        text: str,
        *,
        conversation_state: ConversationState | None = None,
    ) -> tuple[JailbreakSignal, ...]:
        del text, conversation_state
        return (
            JailbreakSignal(
                category="role_play",
                confidence=0.85,
                evidence_reference="ROLE_PLAY_TOKEN",
                detector_id=self.detector_id,
            ),
        )


@pytest.mark.asyncio
async def test_jailbreak_event_fires_with_documented_fields() -> None:
    tracer = RecordingTracer()
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()
    pipeline = GuardPipeline(
        inspectors=[],
        jailbreak_detector=_StubDetector(),
        tracer_hook=tracer,
        logger_hook=logger,
        metrics_hook=metric_sink,
    )

    await pipeline.pre_process(GuardInput(text="anything"))

    detected_events = [e for e in logger.captured_events if e.name == "guard.jailbreak.detected"]
    assert len(detected_events) == 1
    fields = detected_events[0].fields
    assert fields["category"] == "role_play"
    assert fields["confidence"] == 0.85
    assert fields["detector_id"] == "stub-emit:1"


@pytest.mark.asyncio
async def test_jailbreak_counter_increments_with_category_attribute() -> None:
    tracer = RecordingTracer()
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()
    pipeline = GuardPipeline(
        inspectors=[],
        jailbreak_detector=_StubDetector(),
        tracer_hook=tracer,
        logger_hook=logger,
        metrics_hook=metric_sink,
    )

    await pipeline.pre_process(GuardInput(text="anything"))

    counters = [
        m for m in metric_sink.captured_metrics if m.name == "arc_guardrails.jailbreak.detected"
    ]
    assert len(counters) == 1
    assert counters[0].attributes["category"] == "role_play"


@pytest.mark.asyncio
async def test_no_emissions_when_detector_returns_empty() -> None:
    class _NoOp:
        @property
        def detector_id(self) -> str:
            return "noop:1"

        def detect(self, text, *, conversation_state=None):
            return ()

    tracer = RecordingTracer()
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()
    pipeline = GuardPipeline(
        inspectors=[],
        jailbreak_detector=_NoOp(),
        tracer_hook=tracer,
        logger_hook=logger,
        metrics_hook=metric_sink,
    )

    await pipeline.pre_process(GuardInput(text="benign"))

    detected_events = [e for e in logger.captured_events if e.name == "guard.jailbreak.detected"]
    assert detected_events == []
    counters = [
        m for m in metric_sink.captured_metrics if m.name == "arc_guardrails.jailbreak.detected"
    ]
    assert counters == []
