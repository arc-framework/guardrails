"""``log_level_floor`` suppresses stage transitions; failures bypass.

Configures ``log_level_floor="warn"``, runs a request, asserts:

- ``guard.stage.started`` and ``guard.stage.completed`` (both INFO)
  do NOT appear in the captured event list.
- ``guard.stage.failed`` (severity tied to ``FAIL_RULE``) DOES appear
  — failure events bypass the floor entirely.

The bypass list is in ``arc_guard.observability.sampling._FAILURE_EVENT_NAMES``;
this test pins the contract that the floor never silences a failure.
"""

from __future__ import annotations

import pytest
from arc_guard_core.config import GuardConfig
from arc_guard_core.exceptions import InspectorError
from arc_guard_core.observability_config import ObservabilityConfig
from arc_guard_core.types import GuardInput

from arc_guard.observability import (
    RecordingLogger,
    RecordingMetricSink,
    RecordingTracer,
)
from arc_guard.pipeline import GuardPipeline


class _RaisingInspector:
    async def inspect(self, result):  # type: ignore[no-untyped-def]
        raise InspectorError(
            "synthetic inspector fault",
            code="inspector.unhandled",
        )


@pytest.mark.asyncio
async def test_floor_warn_suppresses_info_stage_transitions() -> None:
    config = GuardConfig(
        observability=ObservabilityConfig(log_level_floor="warn"),
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

    await pipeline.pre_process(GuardInput(text="floor test"))

    started = [e for e in logger.captured_events if e.name == "guard.stage.started"]
    completed = [e for e in logger.captured_events if e.name == "guard.stage.completed"]
    failed = [e for e in logger.captured_events if e.name == "guard.stage.failed"]
    run_started = [e for e in logger.captured_events if e.name == "guard.run.started"]
    run_completed = [e for e in logger.captured_events if e.name == "guard.run.completed"]

    # INFO-level events are below the warn floor.
    assert started == []
    assert completed == []
    assert run_started == []
    assert run_completed == []

    # WARN-level failure event always passes through.
    assert len(failed) >= 1, "failure events must bypass the log-level floor"


@pytest.mark.asyncio
async def test_floor_info_default_keeps_stage_transitions() -> None:
    """With the default floor=info, stage transitions are visible."""
    config = GuardConfig(observability=ObservabilityConfig())  # default floor=info
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

    await pipeline.pre_process(GuardInput(text="default floor"))

    started = [e for e in logger.captured_events if e.name == "guard.stage.started"]
    assert len(started) >= 1
