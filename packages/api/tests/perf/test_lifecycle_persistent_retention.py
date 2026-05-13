"""Soak: 25,000 most-recent rids remain queryable after a service restart.

Writes 25,000 distinct rids into a SQLite-backed sink (each with a small
event burst — well under both retention thresholds). Closes the sink to
flush. Re-opens against the same file. Asserts a uniform sample of the
written rids is still queryable.

The default retention thresholds (500,000 rows / 7 days) easily clear
25,000 rids × ~3 events each. This is the floor we promise operators
post-restart; if a future change tightens retention, this test fails
loudly.
"""

from __future__ import annotations

import asyncio
import random
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink
from arc_guard_core.lifecycle import (
    PreProcessStarted,
    RequestCompleted,
    RequestStarted,
    new_event_id,
)

pytestmark = pytest.mark.slow

_RIDS = 25_000
_SAMPLE_SIZE = 500


def _now() -> datetime:
    return datetime.now(UTC)


async def _seed_burst(sink: SqliteLifecycleSink, rid: str) -> None:
    root = RequestStarted(
        id=new_event_id(),
        parent_id=None,
        seq=0,
        ts=_now(),
        rid=rid,
        route="/v1/chat/completions",
        model="echo",
        msg_count=1,
        input_size_bytes=20,
    )
    await sink.emit(root)
    pre = PreProcessStarted(
        id=new_event_id(),
        parent_id=root.id,
        seq=1,
        ts=_now(),
        rid=rid,
        correlation_id="corr-" + rid,
        decision_id="",
    )
    await sink.emit(pre)
    await sink.emit(
        RequestCompleted(
            id=new_event_id(),
            parent_id=root.id,
            seq=2,
            ts=_now(),
            rid=rid,
            blocked=False,
            pre_action="pass",
            post_action="pass",
            total_duration_ms=1.0,
        )
    )


async def _seed_all(sink: SqliteLifecycleSink) -> None:
    for i in range(_RIDS):
        await _seed_burst(sink, f"soak-rid-{i:06d}")


def test_25k_rids_queryable_after_simulated_restart() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "lifecycle.db")

        sink_a = SqliteLifecycleSink(path=path)
        try:
            asyncio.run(_seed_all(sink_a))
            assert len(sink_a) >= _RIDS, (
                f"expected at least {_RIDS} rows after seed, got {len(sink_a)}"
            )
        finally:
            sink_a._conn.close()

        sink_b = SqliteLifecycleSink(path=path)
        try:
            sample = random.sample(range(_RIDS), _SAMPLE_SIZE)
            recovered = 0
            for i in sample:
                rid = f"soak-rid-{i:06d}"
                events = asyncio.run(sink_b.query(rid))
                if events and len(events) >= 3:
                    recovered += 1

            print(
                f"\n[persistent-retention] seeded={_RIDS} sampled={_SAMPLE_SIZE} "
                f"recovered={recovered}/{_SAMPLE_SIZE}"
            )
            assert recovered == _SAMPLE_SIZE, (
                f"only {recovered}/{_SAMPLE_SIZE} sampled rids recoverable after restart"
            )
        finally:
            sink_b._conn.close()
