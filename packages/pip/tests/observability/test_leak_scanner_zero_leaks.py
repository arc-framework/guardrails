"""Payload-leak scanner returns empty list across the 50-input corpus.

Drives the pipeline through every input in
``tests/fixtures/sensitive_inputs.py``, captures all observability
artifacts via the recording sinks, and asserts the leak scanner finds
zero leaks against the original input as a substring source.

The no-leak rule: no raw input text or finding-matched substring may
appear in any span attribute, log field, or metric label.
"""

from __future__ import annotations

import pytest
from arc_guard_core.types import GuardInput

from arc_guard.observability import (
    CapturedArtifacts,
    RecordingLogger,
    RecordingMetricSink,
    RecordingTracer,
    scan_for_leaks,
)
from arc_guard.pipeline import GuardPipeline

from ..fixtures.sensitive_inputs import SENSITIVE_INPUTS


@pytest.mark.asyncio
async def test_leak_scanner_returns_empty_for_full_corpus() -> None:
    tracer = RecordingTracer()
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()
    pipeline = GuardPipeline(
        inspectors=[],
        tracer_hook=tracer,
        logger_hook=logger,
        metrics_hook=metric_sink,
    )

    leaks_per_input: dict[str, int] = {}

    for text in SENSITIVE_INPUTS:
        tracer.clear()
        logger.clear()
        metric_sink.clear()
        await pipeline.pre_process(GuardInput(text=text))

        captured = CapturedArtifacts(
            spans=list(tracer.captured_spans),
            events=list(logger.captured_events),
            metrics=list(metric_sink.captured_metrics),
        )
        # Scan against the original input text. (Findings would also be
        # added when an inspector chain is wired; here we run with empty
        # inspectors so only the input itself is the leak source.)
        leaks = scan_for_leaks(captured, originals=[text])
        if leaks:
            leaks_per_input[text[:60]] = len(leaks)

    assert leaks_per_input == {}, (
        f"payload-leak scanner found leaks for {len(leaks_per_input)} inputs: "
        f"{leaks_per_input}"
    )
