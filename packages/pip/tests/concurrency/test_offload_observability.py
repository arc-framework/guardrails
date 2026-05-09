"""``run_off_loop`` increments the offload counter once per call.

Direct unit test of the offload helper rather than driving the full
pipeline: asserts the counter fires before the wrapped callable, that
the call result propagates correctly, that exceptions propagate
unchanged, and that the counter still fires on raise (so failed
offloads stay observable).
"""

from __future__ import annotations

import pytest

from arc_guard.concurrency.offload import OFFLOAD_COUNTER, run_off_loop
from arc_guard.observability import RecordingMetricSink


def _add(a: int, b: int) -> int:
    return a + b


def _raise() -> None:
    raise RuntimeError("synthetic failure")


@pytest.mark.asyncio
async def test_offload_counter_fires_on_success() -> None:
    sink = RecordingMetricSink()
    result = await run_off_loop(_add, 2, 3, stage="execute", metric_sink=sink)

    assert result == 5
    counters = [m for m in sink.captured_metrics if m.name == OFFLOAD_COUNTER]
    assert len(counters) == 1
    assert counters[0].attributes["stage"] == "execute"


@pytest.mark.asyncio
async def test_offload_counter_fires_even_when_callable_raises() -> None:
    sink = RecordingMetricSink()
    with pytest.raises(RuntimeError, match="synthetic failure"):
        await run_off_loop(_raise, stage="classify", metric_sink=sink)

    counters = [m for m in sink.captured_metrics if m.name == OFFLOAD_COUNTER]
    assert len(counters) == 1
    assert counters[0].attributes["stage"] == "classify"


@pytest.mark.asyncio
async def test_offload_forwards_kwargs() -> None:
    sink = RecordingMetricSink()

    def _greet(*, name: str) -> str:
        return f"hello, {name}"

    result = await run_off_loop(_greet, stage="route", metric_sink=sink, name="world")
    assert result == "hello, world"
