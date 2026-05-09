"""Contract: ``GET /requests`` response envelope matches the documented shape.

Asserts the response body parses cleanly into ``RequestPage``, that an
empty result set returns 200 (not 404), and that ``has_more`` /
``filters`` echo correctly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink
from arc_guard_core.schemas import RequestPage

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


def _seed_summary(
    path: str,
    rid: str,
    *,
    status: str = "completed",
    final_action: str = "pass",
    max_risk: float = 0.1,
    duration_ms: int = 50,
    started_at: datetime | None = None,
) -> None:
    """Bypass the projector — directly insert a row for fast contract setup."""
    if started_at is None:
        started_at = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)
    import sqlite3

    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "INSERT INTO request_summaries"
            " (rid, started_at, last_event_at, status, final_action,"
            "  max_risk, duration_ms, decision_id, live, stage)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 0, 'report')",
            (
                rid,
                started_at.isoformat(),
                started_at.isoformat(),
                status,
                final_action,
                max_risk,
                duration_ms,
            ),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def dashboard_settings(tmp_path: Path) -> ServiceSettings:
    db = tmp_path / "arc_guardrail.db"
    sink = SqliteLifecycleSink(str(db))
    # Drop the connection — the migration is what we need; tests open
    # their own connections.
    import asyncio

    asyncio.get_event_loop().run_until_complete(sink.close()) if False else None
    settings = ServiceSettings(
        enable_chat_completions=False,
        lifecycle_sqlite_path=str(db),
    )
    return settings


@pytest.fixture()
async def client(dashboard_settings: ServiceSettings) -> httpx.AsyncClient:
    app = create_app(dashboard_settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_empty_result_returns_200(client: httpx.AsyncClient) -> None:
    """No matching requests → 200 with items=[], not 404."""
    resp = await client.get("/requests")
    assert resp.status_code == 200
    page = RequestPage.model_validate(resp.json())
    assert page.items == ()
    assert page.total == 0
    assert page.has_more is False


@pytest.mark.asyncio
async def test_envelope_shape_matches_request_page(
    client: httpx.AsyncClient, dashboard_settings: ServiceSettings
) -> None:
    _seed_summary(dashboard_settings.lifecycle_sqlite_path, "01JABC0EVT01")
    resp = await client.get("/requests?page_size=10")
    assert resp.status_code == 200
    page = RequestPage.model_validate(resp.json())
    assert len(page.items) == 1
    assert page.items[0].rid == "01JABC0EVT01"
    assert page.page == 1
    assert page.page_size == 10
    assert page.total == 1
    assert page.has_more is False


@pytest.mark.asyncio
async def test_filters_echoed_in_response(
    client: httpx.AsyncClient, dashboard_settings: ServiceSettings
) -> None:
    _seed_summary(dashboard_settings.lifecycle_sqlite_path, "01JABC0EVT01")
    resp = await client.get("/requests?status=completed&action=pass&rid_prefix=01J")
    assert resp.status_code == 200
    page = RequestPage.model_validate(resp.json())
    assert "completed" in page.filters.status
    assert "pass" in page.filters.action
    assert page.filters.rid_prefix == "01J"


@pytest.mark.asyncio
async def test_oversized_page_size_rejected(
    client: httpx.AsyncClient, dashboard_settings: ServiceSettings
) -> None:
    cap = dashboard_settings.dashboard_max_request_page_size
    resp = await client.get(f"/requests?page_size={cap + 1}")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_503_when_sqlite_path_unset() -> None:
    """No lifecycle_sqlite_path → 503 with Retry-After."""
    settings = ServiceSettings(enable_chat_completions=False, lifecycle_sqlite_path=None)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/requests")
    assert resp.status_code == 503
    assert "retry-after" in {k.lower() for k in resp.headers.keys()}
    body = resp.json()
    assert body["error"]["code"] == "store_unavailable"
