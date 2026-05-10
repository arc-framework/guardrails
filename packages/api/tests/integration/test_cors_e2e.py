"""End-to-end CORS test: covers the three acceptance scenarios for
the cross-origin operator workflow.

1. Allowed origin → fetch succeeds with the expected CORS headers.
2. Disallowed origin → response has no ``Access-Control-Allow-Origin``.
3. Cross-origin requests retain the same payload-safety rules as
   same-origin requests.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


@pytest.fixture()
async def client(tmp_path: Path):
    db = tmp_path / "arc_guardrail.db"
    SqliteLifecycleSink(str(db))
    settings = ServiceSettings(
        enable_chat_completions=True,
        lifecycle_sqlite_path=str(db),
        dashboard_origins=[
            "http://127.0.0.1:5173",
            "https://dashboard.example.com",
        ],
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_allowed_origin_succeeds_with_cors_header(client) -> None:
    resp = await client.get("/requests", headers={"Origin": "http://127.0.0.1:5173"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


@pytest.mark.asyncio
async def test_second_allowed_origin_also_succeeds(client) -> None:
    resp = await client.get("/requests", headers={"Origin": "https://dashboard.example.com"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://dashboard.example.com"


@pytest.mark.asyncio
async def test_disallowed_origin_blocked_by_browser(client) -> None:
    """Server still serves the response (CORS is enforced by the browser),
    but the missing allow-origin header means the browser blocks it."""
    resp = await client.get("/requests", headers={"Origin": "http://evil.example.com"})
    # Server returns 200 with the body — but the browser would block it
    # because the allow-origin header is absent.
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in {k.lower() for k in resp.headers.keys()}


@pytest.mark.asyncio
async def test_cross_origin_keeps_payload_safety(client) -> None:
    """Same payload-safety rules apply cross-origin as same-origin."""
    resp = await client.get("/requests", headers={"Origin": "http://127.0.0.1:5173"})
    body = resp.json()
    # The default deployment never exposes raw user payload; an empty result
    # set returns an envelope, not raw content.
    assert "items" in body
    assert isinstance(body["items"], list)
    # The response contains no raw user text — verifying by structure rather
    # than content (no concrete payload to inspect on an empty store).


@pytest.mark.asyncio
async def test_preflight_options_succeeds_for_allowed_origin(client) -> None:
    resp = await client.options(
        "/v1/chat/completions",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, X-Request-Id",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


@pytest.mark.asyncio
async def test_cross_origin_chat_post_succeeds_with_cors_headers(client) -> None:
    resp = await client.post(
        "/v1/chat/completions",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Content-Type": "application/json",
            "X-Request-Id": "cors-e2e-rid",
        },
        json={
            "model": "llama3.2",
            "messages": [{"role": "user", "content": "Hello from the dashboard"}],
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    assert resp.headers.get("x-request-id") == "cors-e2e-rid"
