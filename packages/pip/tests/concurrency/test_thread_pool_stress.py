"""Sync stress test: 100 concurrent requests on a shared pipeline.

Drives a single ``GuardPipeline`` instance from a
``ThreadPoolExecutor(max_workers=100)`` with 100 distinct inputs.
Asserts every result corresponds to its own input (zero cross-talk),
no shared-state exceptions are raised, and no
``RegistryFrozenError`` fires during steady-state — proving the
frozen-after-construction registries do not interfere with concurrent
reads on the hot path.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import uuid
from dataclasses import replace

import pytest
from arc_guard_core.exceptions import RegistryFrozenError
from arc_guard_core.types import GuardContext, GuardInput

from arc_guard.observability import (
    RecordingLogger,
    RecordingMetricSink,
    RecordingTracer,
)
from arc_guard.pipeline import GuardPipeline

CONCURRENT_REQUESTS = 100


class _PassthroughInspector:
    async def inspect(self, result):  # type: ignore[no-untyped-def]
        return result


def _run_one(pipeline: GuardPipeline, marker: str) -> tuple[str, str]:
    """Run one request synchronously and return (marker, result.text)."""
    text = f"input-marker:{marker}"
    coro = pipeline.pre_process(
        GuardInput(text=text, context=GuardContext(correlation_id=marker)),
    )
    result = asyncio.run(coro)
    return marker, result.text


def test_thread_pool_stress_no_cross_talk() -> None:
    pipeline = GuardPipeline(
        inspectors=[_PassthroughInspector()],
        tracer_hook=RecordingTracer(),
        logger_hook=RecordingLogger(),
        metrics_hook=RecordingMetricSink(),
    )
    markers = [uuid.uuid4().hex for _ in range(CONCURRENT_REQUESTS)]

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as pool:
        futures = [pool.submit(_run_one, pipeline, m) for m in markers]
        outcomes = [f.result(timeout=30) for f in futures]

    # Cross-talk check: every (marker, result.text) pair should still
    # contain its own marker. If two threads stomped on each other's
    # state, marker A would show up in result B's text.
    for marker, text in outcomes:
        assert marker in text, (
            f"cross-talk detected: marker {marker!r} missing from result {text!r}"
        )


def test_thread_pool_stress_does_not_trigger_registry_freeze_error() -> None:
    """Steady-state reads of frozen registries must not raise."""
    pipeline = GuardPipeline(
        inspectors=[_PassthroughInspector()],
    )
    markers = [str(i) for i in range(CONCURRENT_REQUESTS)]

    raised: list[BaseException] = []

    def runner(marker: str) -> None:
        try:
            asyncio.run(
                pipeline.pre_process(GuardInput(text=f"input:{marker}")),
            )
        except RegistryFrozenError as exc:
            raised.append(exc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as pool:
        list(pool.map(runner, markers, timeout=30))

    assert raised == [], (
        f"steady-state runs raised RegistryFrozenError: {raised}"
    )


@pytest.mark.parametrize("worker_count", [10, CONCURRENT_REQUESTS])
def test_immutable_input_shared_safely_across_threads(worker_count: int) -> None:
    """A single ``GuardInput`` shared across threads must yield identical
    results — proves frozen instances are safe to share without locks.
    """
    shared_input = GuardInput(text="shared-input")
    pipeline = GuardPipeline(inspectors=[_PassthroughInspector()])

    def runner(_: int) -> str:
        result = asyncio.run(pipeline.pre_process(shared_input))
        return result.text

    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as pool:
        outputs = list(pool.map(runner, range(worker_count), timeout=30))

    assert all(out == "shared-input" for out in outputs)


# Defensive sanity check: replace() on a frozen Pydantic model raises so
# concurrent accidental mutation is structurally impossible.
def test_replace_does_not_silently_mutate_shared_input() -> None:
    shared = GuardInput(text="original")
    # ``replace`` on a frozen pydantic model returns a NEW instance; the
    # original is not modified. (For mutable copies, use model_copy.)
    new = replace(shared, text="copy")
    assert shared.text == "original"
    assert new.text == "copy"
    assert shared is not new
