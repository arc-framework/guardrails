"""Perf assertions for the dashboard data-plane targets.

Three latency targets:

- ``GET /requests?page=1&page_size=50`` p95 ≤ 200 ms over ≥ 1 000 retained
  requests.
- Workspace-open p95 ≤ 500 ms (one summary lookup + the three subordinate
  resource calls).
- Filtered SSE p95 ≤ 100 ms emit-to-consumer for an active request.

These tests use **generous thresholds** (5x the spec target) so they
don't false-fail on CI runners with variable load while still catching
serious regressions. The strict spec targets are documented for the
operator's benchmark stack (`make docker-up` on a developer laptop) —
verify those manually with `python -m timeit` or wrk-style load
generators.

Marked with the existing ``slow`` marker so CI's default test run
excludes them; opt in with ``pytest -m slow``.
"""

from __future__ import annotations

import sqlite3
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app

pytestmark = pytest.mark.slow


def _seed_n_summaries(path: str, n: int) -> None:
    """Bulk-insert n request_summary rows + matching lifecycle_events for
    realistic table sizes. One commit at the end keeps WAL fsync overhead
    out of the loop."""
    conn = sqlite3.connect(path)
    base_ts = datetime(2026, 5, 9, 0, 0, 0, tzinfo=UTC)
    try:
        rows = []
        for i in range(n):
            rid = f"rid-{i:06d}"
            ts = (base_ts + timedelta(milliseconds=i)).isoformat()
            rows.append((rid, ts, ts, "completed", "pass", 0.1, 50, 0))
        conn.executemany(
            "INSERT INTO request_summaries"
            " (rid, started_at, last_event_at, status, final_action,"
            "  max_risk, duration_ms, live)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def _seed_workspace_resources(path: str, rid: str) -> None:
    """Add a decision + 100 debug entries for the workspace-open test."""
    import json

    conn = sqlite3.connect(path)
    ts = datetime(2026, 5, 9, 14, 0, 0, tzinfo=UTC).isoformat()
    try:
        body = json.dumps({"decision_id": "dec-x", "action": "pass"})
        conn.execute(
            "INSERT INTO decision_records"
            " (rid, decision_id, recorded_at, payload_json, payload_size_bytes)"
            " VALUES (?, 'dec-x', ?, ?, ?)",
            (rid, ts, body, len(body)),
        )
        for i in range(1, 101):
            conn.execute(
                "INSERT INTO debug_entries"
                " (rid, seq, ts, channel, severity, message, metadata_json)"
                " VALUES (?, ?, ?, 'arc_guard.test', 'DEBUG', ?, '{}')",
                (rid, i, ts, f"line {i}"),
            )
        conn.commit()
    finally:
        conn.close()


def _p95(samples: list[float]) -> float:
    samples = sorted(samples)
    idx = int(len(samples) * 0.95)
    return samples[min(idx, len(samples) - 1)]


@pytest.mark.asyncio
async def test_explorer_page_p95(tmp_path: Path) -> None:
    """``/requests`` p95 ≤ 200 ms over 1 000 retained requests.

    Generous test threshold: 1000 ms (5x spec). Real benchmark numbers
    are validated separately on the documented benchmark stack.
    """
    db = tmp_path / "arc_guardrail.db"
    SqliteLifecycleSink(str(db))
    _seed_n_summaries(str(db), 1000)
    settings = ServiceSettings(
        enable_chat_completions=False, lifecycle_sqlite_path=str(db)
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    samples: list[float] = []
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as c:
        # Warmup
        await c.get("/requests?page=1&page_size=50")
        for _ in range(50):
            t0 = time.perf_counter()
            resp = await c.get("/requests?page=1&page_size=50")
            samples.append((time.perf_counter() - t0) * 1000)
            assert resp.status_code == 200
    p95_ms = _p95(samples)
    assert p95_ms < 1000.0, (
        f"explorer p95 {p95_ms:.1f} ms exceeds the test threshold (1000 ms);"
        f" spec target is 200 ms"
    )


@pytest.mark.asyncio
async def test_workspace_open_p95(tmp_path: Path) -> None:
    """Workspace-open p95 ≤ 500 ms (one summary + three resource calls).
    Generous test threshold: 2500 ms (5x spec)."""
    db = tmp_path / "arc_guardrail.db"
    SqliteLifecycleSink(str(db))
    _seed_n_summaries(str(db), 1000)
    _seed_workspace_resources(str(db), "rid-000500")
    settings = ServiceSettings(
        enable_chat_completions=False, lifecycle_sqlite_path=str(db)
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    samples: list[float] = []
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as c:
        await c.get("/requests/rid-000500")
        for _ in range(20):
            t0 = time.perf_counter()
            r1 = await c.get("/requests/rid-000500")
            r2 = await c.get("/requests/rid-000500/decision")
            r3 = await c.get("/requests/rid-000500/debug?page_size=50")
            elapsed = (time.perf_counter() - t0) * 1000
            samples.append(elapsed)
            assert r1.status_code == 200
            assert r2.status_code == 200
            assert r3.status_code == 200
    p95_ms = _p95(samples)
    assert p95_ms < 2500.0, (
        f"workspace-open p95 {p95_ms:.1f} ms exceeds the test threshold;"
        f" spec target is 500 ms"
    )


@pytest.mark.asyncio
async def test_filtered_sse_setup_completes_quickly(
    tmp_path: Path,
) -> None:
    """Filtered SSE emit-to-consumer p95 ≤ 100 ms.

    A realistic emit-to-consumer benchmark requires live event broadcast
    over real network paths — out of scope for an in-process pytest.
    We verify the cheaper proxy: the pre-subscription path (rid
    validation + liveness check + terminal-sentinel emit + close)
    completes quickly enough to not dominate the 100 ms target. We
    pre-seed a ``RequestCompleted`` event so the handler hits the
    short-circuit branch and the stream closes without ever waiting
    on the subscriber queue.
    """
    from arc_guard_core.lifecycle.events import (
        RequestCompleted,
        RequestStarted,
    )

    db = tmp_path / "arc_guardrail.db"
    sink = SqliteLifecycleSink(str(db))
    ts = datetime(2026, 5, 9, 14, 0, 0, tzinfo=UTC)
    try:
        await sink.emit(
            RequestStarted(
                id="ev-1", parent_id=None, seq=1, ts=ts, rid="rid-perf-done"
            )
        )
        await sink.emit(
            RequestCompleted(
                id="ev-2", parent_id="ev-1", seq=2, ts=ts,
                rid="rid-perf-done", blocked=False, pre_action="pass",
                total_duration_ms=10.0,
            )
        )
    finally:
        await sink.close()

    settings = ServiceSettings(
        enable_chat_completions=False, lifecycle_sqlite_path=str(db)
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    samples: list[float] = []
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=5.0
    ) as c:
        for _ in range(20):
            t0 = time.perf_counter()
            # Pre-seeded terminated rid → handler emits the sentinel and
            # closes synchronously. We read until we see "terminated" so
            # the timing covers the full handshake + body delivery, not
            # just connection setup.
            async with c.stream(
                "GET", "/events?rid=rid-perf-done"
            ) as resp:
                assert resp.status_code == 200
                async for chunk in resp.aiter_text():
                    if "terminated" in chunk:
                        break
            samples.append((time.perf_counter() - t0) * 1000)
    p95_ms = _p95(samples)
    assert p95_ms < 500.0, (
        f"filtered-SSE handshake p95 {p95_ms:.1f} ms exceeds the test"
        f" threshold; spec emit-to-consumer target is 100 ms"
    )
