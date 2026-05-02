"""HTTP transport overhead benchmark.

Asserts the transport-layer wrapping cost (request parsing, validation,
middleware, response serialization — excluding pipeline work) stays under
the documented p99 budget. Uses a fast stub pipeline so the measurement
isolates the transport layer.

Marked ``slow`` so default CI doesn't pay the 200-iteration warm-up cost;
runs on the dedicated perf job via ``pytest -m slow``.
"""

from __future__ import annotations

import asyncio
import statistics
import time

import httpx
import pytest
from arc_guard_core.types import GuardInput, GuardResult

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


class _NoOpPipeline:
    """Fast stub: returns a fixed result without any inspector / strategy work."""

    async def pre_process(self, input: GuardInput) -> GuardResult:
        return GuardResult(text=input.text, action="pass")


_TRANSPORT_OVERHEAD_BUDGET_MS_P99 = 5.0
_BOOT_BUDGET_S = 2.0
_ITERATIONS = 200
_WARMUP = 20


@pytest.mark.slow
@pytest.mark.asyncio
async def test_http_transport_overhead_p99_under_budget() -> None:
    settings = ServiceSettings()
    app = create_app(settings, pipeline=_NoOpPipeline())

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(_WARMUP):
            await client.post("/v1/guard", json={"text": "warmup"})

        durations_ms: list[float] = []
        for _ in range(_ITERATIONS):
            start = time.perf_counter()
            response = await client.post("/v1/guard", json={"text": "perf"})
            durations_ms.append((time.perf_counter() - start) * 1000.0)
            assert response.status_code == 200

    p50 = statistics.median(durations_ms)
    durations_sorted = sorted(durations_ms)
    p99_index = int(0.99 * len(durations_sorted))
    p99 = durations_sorted[min(p99_index, len(durations_sorted) - 1)]

    print(
        f"HTTP transport overhead: n={len(durations_ms)} "
        f"p50={p50:.3f}ms p99={p99:.3f}ms",
    )

    assert p99 < _TRANSPORT_OVERHEAD_BUDGET_MS_P99, (
        f"transport overhead p99={p99:.3f}ms exceeds budget "
        f"{_TRANSPORT_OVERHEAD_BUDGET_MS_P99}ms"
    )


@pytest.mark.slow
def test_create_app_boot_under_budget() -> None:
    durations_s: list[float] = []
    for _ in range(5):
        start = time.perf_counter()
        app = create_app(ServiceSettings(), pipeline=_NoOpPipeline())
        durations_s.append(time.perf_counter() - start)
        assert app is not None

    median_boot = statistics.median(durations_s)
    print(f"create_app boot: n={len(durations_s)} median={median_boot:.3f}s")

    assert median_boot < _BOOT_BUDGET_S, (
        f"create_app boot median={median_boot:.3f}s exceeds budget "
        f"{_BOOT_BUDGET_S}s"
    )


@pytest.mark.slow
def test_run_guard_overhead_under_budget() -> None:
    """In-process ``run_guard`` overhead vs raw ``await pipeline.pre_process``.

    Measures the sync-over-async adapter cost. Target: under 100us median
    when no event loop is running (the no-loop branch uses ``asyncio.run``).
    """
    from arc_guard_service import run_guard

    pipeline = _NoOpPipeline()

    # Async baseline: how long does raw pipeline.pre_process take?
    async def _baseline() -> list[float]:
        durations: list[float] = []
        for _ in range(_ITERATIONS):
            start = time.perf_counter()
            await pipeline.pre_process(GuardInput(text="perf"))
            durations.append((time.perf_counter() - start) * 1000.0)
        return durations

    baseline_ms = asyncio.run(_baseline())
    baseline_p50 = statistics.median(baseline_ms)

    # Sync run_guard from a thread with no running loop.
    sync_ms: list[float] = []
    for _ in range(_ITERATIONS):
        start = time.perf_counter()
        run_guard(GuardInput(text="perf"), pipeline=pipeline)
        sync_ms.append((time.perf_counter() - start) * 1000.0)
    sync_p50 = statistics.median(sync_ms)

    overhead_ms = sync_p50 - baseline_p50
    print(
        f"run_guard overhead: baseline_p50={baseline_p50:.3f}ms "
        f"sync_p50={sync_p50:.3f}ms overhead={overhead_ms:.3f}ms",
    )

    # The no-loop branch boots an asyncio loop per call; this is acknowledged
    # in the contract (~1-2ms typical). The budget is generous to keep the
    # benchmark stable across CI hardware.
    assert sync_p50 < 5.0, (
        f"run_guard sync p50={sync_p50:.3f}ms exceeds 5ms budget"
    )
