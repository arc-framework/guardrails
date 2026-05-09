"""Contract: the stale-live sweeper promotes stuck live=1 rows to
``status='errored'`` by emitting ``RequestErrored`` events.

Three properties pinned:

1. A row whose ``last_event_at`` exceeds the configured threshold gets
   flipped to ``live=0 status='errored'`` and a ``RequestErrored`` event
   is recorded.
2. A fresh ``live=1`` row whose ``last_event_at`` is recent stays
   untouched.
3. Running the sweeper twice in succession produces exactly one
   ``RequestErrored`` per stale rid (idempotency).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from arc_guard_core.lifecycle.events import RequestErrored

from arc_guard.observability.composite_lifecycle_sink import (
    CompositeLifecycleSink,
)
from arc_guard.observability.request_summary_projector import (
    RequestSummaryProjector,
)
from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink
from arc_guard.observability.stale_live_sweeper import StaleLiveSweeper


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _seed_summary(
    path: Path, rid: str, *, last_event_at: datetime, live: int = 1
) -> None:
    """Insert a request_summaries row directly. Mirrors what the projector
    would write for a partially-completed run."""
    started_iso = _iso(last_event_at - timedelta(seconds=5))
    last_iso = _iso(last_event_at)
    with sqlite3.connect(str(path), isolation_level=None) as conn:
        conn.execute(
            "INSERT INTO request_summaries"
            " (rid, started_at, last_event_at, status, live, max_risk, duration_ms)"
            " VALUES (?, ?, ?, 'live', ?, NULL, NULL)",
            (rid, started_iso, last_iso, live),
        )


async def _build_stack(
    path: Path,
) -> tuple[CompositeLifecycleSink, StaleLiveSweeper]:
    """Build the same composite stack the api wires in production:
    SqliteLifecycleSink + RequestSummaryProjector + StaleLiveSweeper.
    Sweeper is configured with `sweep_interval_seconds=0` so its
    background loop never starts — we drive `_run_sweep_once` directly."""
    sqlite_sink = SqliteLifecycleSink(path=str(path))
    projector = RequestSummaryProjector(path=str(path))
    sweeper = StaleLiveSweeper(
        path=str(path),
        lifecycle_sink=None,
        stale_threshold_seconds=600,
        sweep_interval_seconds=60,
    )
    composite = CompositeLifecycleSink([sqlite_sink, projector, sweeper])
    sweeper._sink = composite  # type: ignore[attr-defined]
    return composite, sweeper


def _row(path: Path, rid: str) -> tuple[str, int] | None:
    with sqlite3.connect(str(path)) as conn:
        cur = conn.execute(
            "SELECT status, live FROM request_summaries WHERE rid = ?", (rid,)
        )
        return cur.fetchone()


def _request_errored_count(path: Path, rid: str) -> int:
    with sqlite3.connect(str(path)) as conn:
        cur = conn.execute(
            "SELECT COUNT(*) FROM lifecycle_events"
            " WHERE rid = ? AND event_type = 'RequestErrored'",
            (rid,),
        )
        return int(cur.fetchone()[0])


@pytest.mark.asyncio
async def test_stale_row_promoted_to_errored(tmp_path: Path) -> None:
    db = tmp_path / "arc_guardrail.db"
    composite, sweeper = await _build_stack(db)
    rid = "stale-rid-1"
    _seed_summary(
        db, rid, last_event_at=datetime.now(UTC) - timedelta(seconds=900)
    )

    promoted = await sweeper._run_sweep_once()

    assert promoted == 1
    row = _row(db, rid)
    assert row == ("errored", 0), f"expected errored/0, got {row!r}"
    assert _request_errored_count(db, rid) == 1
    await composite.close()


@pytest.mark.asyncio
async def test_fresh_row_stays_untouched(tmp_path: Path) -> None:
    db = tmp_path / "arc_guardrail.db"
    composite, sweeper = await _build_stack(db)
    rid = "fresh-rid-1"
    _seed_summary(
        db, rid, last_event_at=datetime.now(UTC) - timedelta(seconds=10)
    )

    promoted = await sweeper._run_sweep_once()

    assert promoted == 0
    row = _row(db, rid)
    assert row == ("live", 1), f"expected live/1, got {row!r}"
    assert _request_errored_count(db, rid) == 0
    await composite.close()


@pytest.mark.asyncio
async def test_sweeper_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "arc_guardrail.db"
    composite, sweeper = await _build_stack(db)
    rid = "stale-rid-2"
    _seed_summary(
        db, rid, last_event_at=datetime.now(UTC) - timedelta(seconds=900)
    )

    first = await sweeper._run_sweep_once()
    second = await sweeper._run_sweep_once()

    assert first == 1
    assert second == 0, "second sweep should find no stale rows"
    assert _request_errored_count(db, rid) == 1
    await composite.close()


@pytest.mark.asyncio
async def test_request_errored_event_carries_documented_fields(
    tmp_path: Path,
) -> None:
    db = tmp_path / "arc_guardrail.db"
    composite, sweeper = await _build_stack(db)
    rid = "stale-rid-3"
    _seed_summary(
        db, rid, last_event_at=datetime.now(UTC) - timedelta(seconds=900)
    )

    await sweeper._run_sweep_once()

    events = await composite.query(rid)
    assert events is not None
    erroreds = [e for e in events if isinstance(e, RequestErrored)]
    assert len(erroreds) == 1
    ev = erroreds[0]
    assert ev.reason == "stale_live_sweep"
    assert ev.terminated_by == "stale_live_sweeper"
    assert ev.last_event_seq >= 0
    await composite.close()


@pytest.mark.asyncio
async def test_sweeper_disabled_when_interval_non_positive(
    tmp_path: Path,
) -> None:
    """Setting sweep_interval_seconds <= 0 keeps the background task off."""
    db = tmp_path / "arc_guardrail.db"
    SqliteLifecycleSink(path=str(db))  # ensure schema exists
    sweeper = StaleLiveSweeper(
        path=str(db),
        lifecycle_sink=None,
        stale_threshold_seconds=600,
        sweep_interval_seconds=0,
    )
    sweeper.start_cleanup_task()
    assert sweeper._task is None
    await sweeper.close()
