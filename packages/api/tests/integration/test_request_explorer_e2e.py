"""End-to-end test: dashboard explorer page covers the four acceptance scenarios.

1. Captured requests → 200 with paginated rows.
2. Filters narrow the result set.
3. Live request rows carry the current stage and ``live=True``.
4. Empty result set → 200 with empty items array (never 404).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink
from arc_guard_core.schemas import RequestPage

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


def _seed(
    path: str,
    rid: str,
    *,
    status: str = "completed",
    final_action: str = "pass",
    max_risk: float = 0.1,
    live: bool = False,
    stage: str = "report",
    started_at: datetime | None = None,
) -> None:
    if started_at is None:
        started_at = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "INSERT INTO request_summaries"
            " (rid, started_at, last_event_at, status, final_action,"
            "  max_risk, duration_ms, decision_id, live, stage)"
            " VALUES (?, ?, ?, ?, ?, ?, 50, NULL, ?, ?)",
            (
                rid,
                started_at.isoformat(),
                started_at.isoformat(),
                status,
                final_action,
                max_risk,
                1 if live else 0,
                stage,
            ),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
async def client(tmp_path: Path):
    db = tmp_path / "arc_guardrail.db"
    SqliteLifecycleSink(str(db))  # run migration
    settings = ServiceSettings(enable_chat_completions=False, lifecycle_sqlite_path=str(db))
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, str(db)


@pytest.mark.asyncio
async def test_us1_acceptance_1_paginated_rows(client) -> None:
    c, db = client
    for i in range(75):
        _seed(db, f"rid-{i:03d}")
    resp = await c.get("/requests?page=1&page_size=50")
    assert resp.status_code == 200
    page = RequestPage.model_validate(resp.json())
    assert len(page.items) == 50
    assert page.total == 75
    assert page.has_more is True


@pytest.mark.asyncio
async def test_us1_acceptance_2_filter_narrows_result(client) -> None:
    c, db = client
    _seed(db, "rid-pass", final_action="pass", max_risk=0.05)
    _seed(db, "rid-block", final_action="block", max_risk=0.95)
    resp = await c.get("/requests?action=block")
    page = RequestPage.model_validate(resp.json())
    assert {item.rid for item in page.items} == {"rid-block"}


@pytest.mark.asyncio
async def test_us1_acceptance_3_live_request_carries_stage(client) -> None:
    c, db = client
    _seed(
        db,
        "rid-live",
        status="live",
        final_action="pass",
        live=True,
        stage="classify",
    )
    resp = await c.get("/requests?status=live")
    page = RequestPage.model_validate(resp.json())
    assert len(page.items) == 1
    item = page.items[0]
    assert item.live is True
    assert item.stage == "classify"


@pytest.mark.asyncio
async def test_us1_acceptance_4_empty_result_returns_200(client) -> None:
    c, _ = client
    resp = await c.get("/requests?rid_prefix=does-not-exist")
    assert resp.status_code == 200
    page = RequestPage.model_validate(resp.json())
    assert page.items == ()
    assert page.total == 0
