"""ReporterError is fail-open; result unaffected, observability fires.

Per the foundation, ``ReporterError`` declares ``__failure_mode__ =
"open"``. When a reporter raises during dispatch, the guard result
returned to the caller is unchanged, ``guard.stage.failed`` fires at
WARN with ``stage=report`` / ``posture=open``, and the
``arc_guardrails.stage.failed`` counter increments.
"""

from __future__ import annotations

import asyncio

import pytest
from arc_guard_core.exceptions import ReporterError
from arc_guard_core.types import GuardInput, GuardResult

from arc_guard.observability import (
    RecordingLogger,
    RecordingMetricSink,
    RecordingTracer,
)
from arc_guard.pipeline import GuardPipeline


class _RaisingReporter:
    """Reporter that always raises ReporterError on dispatch."""

    async def report(self, result: GuardResult) -> None:
        raise ReporterError(
            "synthetic reporter fault",
            code="reporter.publish_failed",
        )

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_reporter_failure_is_fail_open() -> None:
    tracer = RecordingTracer()
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()
    pipeline = GuardPipeline(
        inspectors=[],
        reporter=_RaisingReporter(),
        tracer_hook=tracer,
        logger_hook=logger,
        metrics_hook=metric_sink,
    )

    result = await pipeline.pre_process(GuardInput(text="reporter fault test"))

    # Drain the fire-and-forget reporter task so its emissions land in
    # the recording sinks before we assert.
    pending = [t for t in asyncio.all_tasks() if not t.done()]
    pending = [t for t in pending if t is not asyncio.current_task()]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    # Guard result is unaffected by the reporter failure — no refusal,
    # action stays ``pass``.
    assert result.refusal is None
    assert result.action == "pass"

    # stage.failed fires for the report stage at WARN level with
    # posture=open.
    failed_events = [
        e
        for e in logger.captured_events
        if e.name == "guard.stage.failed" and e.fields.get("stage") == "report"
    ]
    assert len(failed_events) == 1
    event = failed_events[0]
    assert event.level == "warn"
    assert event.fields["posture"] == "open"
    assert event.fields["failure_class"] == "reporter"
    assert event.fields["exception_type"] == "ReporterError"

    # Counter increment.
    failed_counters = [
        m
        for m in metric_sink.captured_metrics
        if m.name == "arc_guardrails.stage.failed" and m.attributes.get("stage") == "report"
    ]
    assert len(failed_counters) == 1
    assert failed_counters[0].attributes["posture"] == "open"
