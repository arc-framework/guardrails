"""Contract: read-only enforcement on the four dashboard routes.

The dashboard data plane is strictly GET-only; any mutation method
(``POST`` / ``PUT`` / ``DELETE`` / ``PATCH``) MUST return HTTP 405
Method Not Allowed. The CORS allow-list separately restricts methods
to GET/OPTIONS at the browser layer; this test exercises the
server-side guarantee that holds even when CORS is bypassed.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app

_ROUTES = (
    "/requests",
    "/requests/some-rid",
    "/requests/some-rid/decision",
    "/requests/some-rid/debug",
)
_MUTATION_METHODS = ("POST", "PUT", "DELETE", "PATCH")


@pytest.fixture()
async def client(tmp_path: Path):
    db = tmp_path / "arc_guardrail.db"
    SqliteLifecycleSink(str(db))
    settings = ServiceSettings(enable_chat_completions=False, lifecycle_sqlite_path=str(db))
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.parametrize("route", _ROUTES)
@pytest.mark.parametrize("method", _MUTATION_METHODS)
@pytest.mark.asyncio
async def test_mutation_method_returns_405(client, route: str, method: str) -> None:
    resp = await client.request(method, route)
    assert resp.status_code == 405, f"{method} {route} returned {resp.status_code}; expected 405"
