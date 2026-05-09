"""No captured artifact has a raw-payload field name (schema check).

Drives the pipeline against the sensitive corpus, captures every
artifact, and asserts that no captured field name matches a known
raw-payload pattern. Pairs with the substring-based leak scanner in
``test_leak_scanner_zero_leaks.py`` — the leak scanner catches *value*
contamination; this test catches *schema* mistakes (someone adds a
``"text"`` or ``"input_text"`` attribute by accident).
"""

from __future__ import annotations

import pytest
from arc_guard_core.types import GuardInput

from arc_guard.observability import (
    RecordingLogger,
    RecordingMetricSink,
    RecordingTracer,
)
from arc_guard.pipeline import GuardPipeline

# Field names that historically have leaked raw input/output text or
# matched substrings. None of these should appear as keys in any
# captured artifact.
FORBIDDEN_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "text",
        "input",
        "input_text",
        "output",
        "output_text",
        "body",
        "value",  # too generic — could leak
        "matched",
        "matched_text",
        "matched_substring",
        "raw",
        "payload",
        "user_text",
    }
)


@pytest.mark.asyncio
async def test_no_captured_artifact_has_a_forbidden_field_name() -> None:
    tracer = RecordingTracer()
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()
    pipeline = GuardPipeline(
        inspectors=[],
        tracer_hook=tracer,
        logger_hook=logger,
        metrics_hook=metric_sink,
    )

    await pipeline.pre_process(GuardInput(text="Hello, schema check."))

    offenses: list[str] = []
    for span in tracer.captured_spans:
        for key in span.attributes:
            if key in FORBIDDEN_FIELD_NAMES:
                offenses.append(f"span:{span.name}:attributes.{key}")
    for event in logger.captured_events:
        for key in event.fields:
            if key in FORBIDDEN_FIELD_NAMES:
                offenses.append(f"event:{event.name}:fields.{key}")
    for metric in metric_sink.captured_metrics:
        for key in metric.attributes:
            if key in FORBIDDEN_FIELD_NAMES:
                offenses.append(f"metric:{metric.name}:attributes.{key}")

    assert offenses == [], (
        "captured observability artifacts contain forbidden field names "
        f"(possible raw-payload leak): {offenses}"
    )
