"""Performance: GET /lifecycle/{rid} p95 latency from the in-memory tier.

Pre-populates the ring buffer with 4000 distinct rids × 20 events each
(80,000 events resident — close to the 5,000-request default capacity),
then measures `GET /lifecycle/{rid}` over 100 trials. p95 must stay
under 50 ms wall-clock per the documented contract.

Marked `slow` so it runs only when explicitly invoked
(`pytest -m slow tests/perf/test_lifecycle_lookup_latency.py`); the
default test run skips it. Keeps CI fast while preserving the perf
guardrail when needed.
"""

from __future__ import annotations

import asyncio
import random
import statistics
import time
from datetime import UTC, datetime

import pytest
from arc_guard_core.lifecycle import (
    BackendCalled,
    BackendResponded,
    DecisionEmitted,
    FindingProduced,
    InspectorRan,
    PreProcessCompleted,
    PreProcessStarted,
    RequestCompleted,
    RequestStarted,
    StageRan,
    new_event_id,
)
from fastapi.testclient import TestClient

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app

pytestmark = pytest.mark.slow


def _now() -> datetime:
    return datetime.now(UTC)


def _populate_one_request(sink, rid: str) -> None:
    """Fill one rid with 20 typed events approximating a full chat-completion
    flow. Constructs events directly (no pipeline) for fast pre-population."""
    seq = 0

    def _next_seq() -> int:
        nonlocal seq
        s = seq
        seq += 1
        return s

    asyncio.run(_emit_burst(sink, rid, _next_seq))


async def _emit_burst(sink, rid: str, next_seq) -> None:
    root = RequestStarted(
        id=new_event_id(),
        parent_id=None,
        seq=next_seq(),
        ts=_now(),
        rid=rid,
        route="/v1/chat/completions",
        model="echo",
        msg_count=1,
        input_size_bytes=42,
    )
    await sink.emit(root)

    pre = PreProcessStarted(
        id=new_event_id(),
        parent_id=root.id,
        seq=next_seq(),
        ts=_now(),
        rid=rid,
        correlation_id="corr-" + rid,
        decision_id="",
    )
    await sink.emit(pre)

    # 12 stages worth of StageRan + a couple inspector / finding events.
    for stage in (
        "validate",
        "defend",
        "classify",
        "deception_inspect",
        "sanitize",
        "route",
        "execute",
        "verify",
        "rehydrate",
        "decision_emit",
        "report",
    ):
        await sink.emit(
            StageRan(
                id=new_event_id(),
                parent_id=pre.id,
                seq=next_seq(),
                ts=_now(),
                rid=rid,
                stage=stage,  # type: ignore[arg-type]
                duration_ms=0.5,
                status="ok",
            )
        )

    insp = InspectorRan(
        id=new_event_id(),
        parent_id=pre.id,
        seq=next_seq(),
        ts=_now(),
        rid=rid,
        name="PresidioInspector",
        duration_ms=24.7,
        findings_count=1,
    )
    await sink.emit(insp)
    await sink.emit(
        FindingProduced(
            id=new_event_id(),
            parent_id=insp.id,
            seq=next_seq(),
            ts=_now(),
            rid=rid,
            entity_type="EMAIL_ADDRESS",
            span=(12, 29),
            score=1.0,
            risk_level=3,
            inspector="presidio",
        )
    )

    bc = BackendCalled(
        id=new_event_id(),
        parent_id=root.id,
        seq=next_seq(),
        ts=_now(),
        rid=rid,
        backend="echo",
        url="echo://local",
        payload_msg_count=1,
    )
    await sink.emit(bc)
    await sink.emit(
        BackendResponded(
            id=new_event_id(),
            parent_id=bc.id,
            seq=next_seq(),
            ts=_now(),
            rid=rid,
            duration_ms=3442.1,
            http_status=200,
            response_msg_chars=183,
            response_finish_reason="stop",
            swap_origin_id=None,
        )
    )

    await sink.emit(
        DecisionEmitted(
            id=new_event_id(),
            parent_id=pre.id,
            seq=next_seq(),
            ts=_now(),
            rid=rid,
            action="pass",
            max_risk="LOW",
            decision_id="dec_" + rid,
            bypass_reason=None,
        )
    )

    await sink.emit(
        PreProcessCompleted(
            id=new_event_id(),
            parent_id=pre.id,
            seq=next_seq(),
            ts=_now(),
            rid=rid,
            action="pass",
            blocked=False,
            total_duration_ms=10.0,
        )
    )

    await sink.emit(
        RequestCompleted(
            id=new_event_id(),
            parent_id=root.id,
            seq=next_seq(),
            ts=_now(),
            rid=rid,
            blocked=False,
            pre_action="pass",
            post_action="pass",
            total_duration_ms=20.0,
        )
    )


def test_lookup_p95_under_50ms_with_4000_resident_rids() -> None:
    """Pre-populate ring with 4000 rids; measure 100 lookups; assert p95 < 50ms."""
    settings = ServiceSettings(
        backend="echo",
        lifecycle_buffer_capacity=5000,
        lifecycle_sqlite_path=None,  # ring-only — isolate in-memory tier perf
    )
    with TestClient(create_app(settings)) as client:
        sink = client.app.state.arc_guard_lifecycle_sink

        # Pre-populate: 4000 distinct rids × ~17 events each.
        rids = [f"perf-rid-{i:04d}" for i in range(4000)]
        for rid in rids:
            _populate_one_request(sink, rid)

        # Sample 100 random rids; measure GET /lifecycle/{rid} wall-clock.
        sample = random.sample(rids, 100)
        latencies_ms: list[float] = []
        for rid in sample:
            t0 = time.perf_counter()
            r = client.get(f"/lifecycle/{rid}")
            elapsed_ms = (time.perf_counter() - t0) * 1000
            assert r.status_code == 200, f"lookup {rid} failed: {r.status_code}"
            latencies_ms.append(elapsed_ms)

        latencies_ms.sort()
        p50 = statistics.median(latencies_ms)
        p95 = latencies_ms[int(0.95 * len(latencies_ms))]
        max_ms = latencies_ms[-1]
        print(
            f"\n[lifecycle-lookup] 100 trials over 4000 resident rids: "
            f"p50={p50:.2f}ms p95={p95:.2f}ms max={max_ms:.2f}ms"
        )
        assert p95 < 50.0, f"p95 lookup latency exceeded 50 ms: {p95:.2f} ms"
