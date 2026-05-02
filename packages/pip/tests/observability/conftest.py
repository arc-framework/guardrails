"""Fixtures for the observability test suite.

Provides recording sinks (tracer / logger / metric sink) and a pipeline
pre-wired to use them so individual test files can focus on their
assertions.
"""

from __future__ import annotations

import pytest

from arc_guard.observability import (
    RecordingLogger,
    RecordingMetricSink,
    RecordingTracer,
)


@pytest.fixture
def recording_sinks() -> tuple[RecordingTracer, RecordingLogger, RecordingMetricSink]:
    """A fresh trio of recording sinks per test."""
    return RecordingTracer(), RecordingLogger(), RecordingMetricSink()
