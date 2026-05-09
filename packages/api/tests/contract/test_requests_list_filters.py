"""Contract: ``GET /requests`` filter semantics.

Covers:
- ``rid_prefix`` is case-sensitive prefix match (no substring, no regex).
- Time-window filters use inclusive ``since`` / exclusive ``until``.
- Repeated enum filters (``?status=A&status=B``) are OR-combined.
- Unknown enum values return HTTP 400 with ``invalid_query``.
- SQLite LIKE wildcards inside ``rid_prefix`` are escaped (no injection).
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
            " VALUES (?, ?, ?, ?, ?, ?, 50, NULL, 0, 'report')",
            (
                rid,
                started_at.isoformat(),
                started_at.isoformat(),
                status,
                final_action,
                max_risk,
            ),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def dashboard_settings(tmp_path: Path) -> ServiceSettings:
    db = tmp_path / "arc_guardrail.db"
    SqliteLifecycleSink(str(db))  # run migration; we don't keep the sink
    return ServiceSettings(
        enable_chat_completions=False, lifecycle_sqlite_path=str(db)
    )


@pytest.fixture()
async def client(dashboard_settings: ServiceSettings) -> httpx.AsyncClient:
    app = create_app(dashboard_settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_rid_prefix_is_case_sensitive(
    client: httpx.AsyncClient, dashboard_settings: ServiceSettings
) -> None:
    db = dashboard_settings.lifecycle_sqlite_path
    _seed(db, "ABC123XYZ")
    _seed(db, "abc123xyz")
    resp_upper = await client.get("/requests?rid_prefix=ABC")
    page_upper = RequestPage.model_validate(resp_upper.json())
    assert {item.rid for item in page_upper.items} == {"ABC123XYZ"}
    resp_lower = await client.get("/requests?rid_prefix=abc")
    page_lower = RequestPage.model_validate(resp_lower.json())
    assert {item.rid for item in page_lower.items} == {"abc123xyz"}


@pytest.mark.asyncio
async def test_rid_prefix_no_substring_match(
    client: httpx.AsyncClient, dashboard_settings: ServiceSettings
) -> None:
    db = dashboard_settings.lifecycle_sqlite_path
    _seed(db, "ABC123XYZ")
    # "123" appears INSIDE "ABC123XYZ" but rid_prefix is prefix-only.
    resp = await client.get("/requests?rid_prefix=123")
    page = RequestPage.model_validate(resp.json())
    assert page.items == ()


@pytest.mark.asyncio
async def test_rid_prefix_escapes_like_wildcards(
    client: httpx.AsyncClient, dashboard_settings: ServiceSettings
) -> None:
    """A user-supplied '%' is matched literally, not as a SQL wildcard."""
    db = dashboard_settings.lifecycle_sqlite_path
    _seed(db, "ABC123")
    _seed(db, "%literal")
    resp = await client.get("/requests?rid_prefix=%25literal")  # url-encoded %
    page = RequestPage.model_validate(resp.json())
    assert {item.rid for item in page.items} == {"%literal"}


@pytest.mark.asyncio
async def test_time_window_inclusive_since_exclusive_until(
    client: httpx.AsyncClient, dashboard_settings: ServiceSettings
) -> None:
    db = dashboard_settings.lifecycle_sqlite_path
    _seed(db, "rid-09", started_at=datetime(2026, 5, 9, tzinfo=UTC))
    _seed(db, "rid-10", started_at=datetime(2026, 5, 10, tzinfo=UTC))
    _seed(db, "rid-11", started_at=datetime(2026, 5, 11, tzinfo=UTC))
    resp = await client.get(
        "/requests?since=2026-05-10T00:00:00%2B00:00&until=2026-05-11T00:00:00%2B00:00"
    )
    page = RequestPage.model_validate(resp.json())
    assert {item.rid for item in page.items} == {"rid-10"}


@pytest.mark.asyncio
async def test_repeated_status_filter_or_combined(
    client: httpx.AsyncClient, dashboard_settings: ServiceSettings
) -> None:
    db = dashboard_settings.lifecycle_sqlite_path
    _seed(db, "rid-live", status="live")
    _seed(db, "rid-completed", status="completed")
    _seed(db, "rid-errored", status="errored")
    resp = await client.get("/requests?status=live&status=errored")
    page = RequestPage.model_validate(resp.json())
    assert {item.rid for item in page.items} == {"rid-live", "rid-errored"}


@pytest.mark.asyncio
async def test_unknown_status_returns_400(
    client: httpx.AsyncClient,
) -> None:
    resp = await client.get("/requests?status=ghost")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_unknown_action_returns_400(
    client: httpx.AsyncClient,
) -> None:
    resp = await client.get("/requests?action=telekinesis")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_unknown_risk_band_returns_400(
    client: httpx.AsyncClient,
) -> None:
    resp = await client.get("/requests?risk_band=infinite")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_risk_band_low_filters_correctly(
    client: httpx.AsyncClient, dashboard_settings: ServiceSettings
) -> None:
    db = dashboard_settings.lifecycle_sqlite_path
    _seed(db, "rid-low", max_risk=0.1)
    _seed(db, "rid-med", max_risk=0.6)
    _seed(db, "rid-high", max_risk=0.9)
    resp = await client.get("/requests?risk_band=low")
    page = RequestPage.model_validate(resp.json())
    assert {item.rid for item in page.items} == {"rid-low"}


@pytest.mark.asyncio
async def test_risk_band_high_filters_correctly(
    client: httpx.AsyncClient, dashboard_settings: ServiceSettings
) -> None:
    db = dashboard_settings.lifecycle_sqlite_path
    _seed(db, "rid-low", max_risk=0.1)
    _seed(db, "rid-high", max_risk=0.92)
    resp = await client.get("/requests?risk_band=high")
    page = RequestPage.model_validate(resp.json())
    assert {item.rid for item in page.items} == {"rid-high"}
