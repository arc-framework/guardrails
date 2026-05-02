"""Recursive guard invocation propagates ``parent_run_correlation_id``.

A strategy stub that re-enters the guard from inside its own
processing should produce two distinct ``guard.run.started`` events:
the inner one carrying the outer run's correlation_id as
``parent_run_correlation_id``. The outer run, with no enclosing
context, has no parent.

Uses a custom ``Inspector`` that calls ``pipeline.pre_process`` on a
nested input from inside its ``inspect`` body. The contextvars-based
parent tracking handles the link automatically — no parameter
threading required.
"""

from __future__ import annotations

import pytest
from arc_guard_core.types import GuardContext, GuardInput

from arc_guard.observability import (
    RecordingLogger,
    RecordingMetricSink,
    RecordingTracer,
)
from arc_guard.pipeline import GuardPipeline


class _RecursiveInspector:
    """Inspector that re-enters the pipeline once on the first call.

    The recursion is single-level so the test can clearly observe
    the outer run + one inner run; deeper recursion would work the
    same way but adds noise to the assertion.
    """

    def __init__(self) -> None:
        self.pipeline: GuardPipeline | None = None
        self._called = False

    async def inspect(self, result):  # type: ignore[no-untyped-def]
        if self.pipeline is None or self._called:
            return result
        self._called = True
        # Recursive re-entry: the same task runs both calls, so the
        # contextvar carries the outer correlation_id forward.
        await self.pipeline.pre_process(GuardInput(text="inner-recursive-call"))
        return result


@pytest.mark.asyncio
async def test_inner_run_records_parent_correlation_id() -> None:
    inspector = _RecursiveInspector()
    logger = RecordingLogger()
    pipeline = GuardPipeline(
        inspectors=[inspector],
        tracer_hook=RecordingTracer(),
        logger_hook=logger,
        metrics_hook=RecordingMetricSink(),
    )
    inspector.pipeline = pipeline  # close the cycle for the inspector

    await pipeline.pre_process(
        GuardInput(text="outer-call", context=GuardContext(correlation_id="outer-corr")),
    )

    started_events = [e for e in logger.captured_events if e.name == "guard.run.started"]
    assert len(started_events) == 2, (
        f"expected outer + inner guard.run.started events, got {len(started_events)}"
    )

    outer = next(e for e in started_events if e.fields["correlation_id"] == "outer-corr")
    inner = next(e for e in started_events if e.fields["correlation_id"] != "outer-corr")

    # Outer run has no enclosing context — no parent_run_correlation_id.
    assert "parent_run_correlation_id" not in outer.fields

    # Inner run carries the outer run's id as its parent.
    assert inner.fields.get("parent_run_correlation_id") == "outer-corr"
    assert inner.fields["correlation_id"] != "outer-corr"


@pytest.mark.asyncio
async def test_sequential_top_level_runs_have_no_parent() -> None:
    """Two same-task pre_process calls in sequence (not nested)
    must NOT see each other as parent — the contextvar resets between
    runs.
    """
    pipeline = GuardPipeline(
        inspectors=[],
        tracer_hook=RecordingTracer(),
        logger_hook=(logger := RecordingLogger()),
        metrics_hook=RecordingMetricSink(),
    )
    await pipeline.pre_process(
        GuardInput(text="first", context=GuardContext(correlation_id="first-corr")),
    )
    await pipeline.pre_process(
        GuardInput(text="second", context=GuardContext(correlation_id="second-corr")),
    )

    started = [e for e in logger.captured_events if e.name == "guard.run.started"]
    assert len(started) == 2
    for event in started:
        assert "parent_run_correlation_id" not in event.fields, (
            f"sequential top-level run should not have a parent: {event.fields}"
        )
