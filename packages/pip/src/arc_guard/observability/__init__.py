"""Observability glue for arc-guard.

Holds the stage-instrumentation wrapper, recording sinks for testing,
the default attribute redactor, and the leak scanner. Concrete OTEL
backends live in ``arc_guard.middleware.otel`` and are gated by the
``arc-guard[otel]`` install extra.

This sub-package is intentionally importable from production code so
downstream specs (rehydration, jailbreak, eval) can reuse the recording
sinks and leak scanner in their own test suites.
"""

from __future__ import annotations

from arc_guard.observability.attributes import (
    REASON_CONTAINS_INPUT_SUBSTRING,
    REASON_EXCEEDS_BYTE_CAP,
    REASON_NOT_IN_ALLOW_LIST,
    BoundedRedactor,
)
from arc_guard.observability.leak_scanner import LeakReport, scan_for_leaks
from arc_guard.observability.recording import (
    CapturedArtifacts,
    CapturedEvent,
    CapturedMetric,
    CapturedSpan,
    RecordingLogger,
    RecordingMetricSink,
    RecordingTracer,
)
from arc_guard.observability.stage_runner import stage_runner

__all__ = [
    "CapturedSpan",
    "CapturedEvent",
    "CapturedMetric",
    "CapturedArtifacts",
    "RecordingTracer",
    "RecordingLogger",
    "RecordingMetricSink",
    "stage_runner",
    "BoundedRedactor",
    "REASON_NOT_IN_ALLOW_LIST",
    "REASON_EXCEEDS_BYTE_CAP",
    "REASON_CONTAINS_INPUT_SUBSTRING",
    "LeakReport",
    "scan_for_leaks",
]
