"""Contract: CORS middleware shape matches the documented configuration.

Verified end-to-end via the actual middleware wiring in ``create_app`` —
not by introspecting middleware internals (Starlette/FastAPI don't expose
them stably).

Also asserts negative coverage: when ``dashboard_origins`` is empty, no
CORS middleware is installed and disallowed origins receive no
``Access-Control-Allow-Origin`` header.
"""

from __future__ import annotations

import httpx
import pytest

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


@pytest.fixture()
async def allowed_client():
    settings = ServiceSettings(
        enable_chat_completions=False,
        lifecycle_sqlite_path=None,
        dashboard_origins=["http://127.0.0.1:5173"],
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_allowed_origin_gets_cors_headers(allowed_client) -> None:
    resp = await allowed_client.get("/requests", headers={"Origin": "http://127.0.0.1:5173"})
    # Even though /requests returns 503 (no sqlite path), the CORS layer
    # still adds the allow-origin header.
    assert resp.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


@pytest.mark.asyncio
async def test_disallowed_origin_gets_no_allow_header(allowed_client) -> None:
    resp = await allowed_client.get("/requests", headers={"Origin": "http://evil.example.com"})
    assert "access-control-allow-origin" not in {k.lower() for k in resp.headers.keys()}


@pytest.mark.asyncio
async def test_preflight_advertises_get_options_only(allowed_client) -> None:
    resp = await allowed_client.options(
        "/requests",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Cache-Control",
        },
    )
    methods = resp.headers.get("access-control-allow-methods", "")
    methods_set = {m.strip() for m in methods.split(",") if m.strip()}
    assert methods_set == {"GET", "OPTIONS"}


@pytest.mark.asyncio
async def test_preflight_advertises_three_allowed_headers(allowed_client) -> None:
    """Starlette's CORSMiddleware appends the CORS-safelisted request
    headers (accept, accept-language, content-language) per spec — those
    are always allowed without preflight. We require our three to be
    present, not that the set is exact."""
    resp = await allowed_client.options(
        "/requests",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Cache-Control",
        },
    )
    allowed = resp.headers.get("access-control-allow-headers", "")
    allowed_set = {h.strip().lower() for h in allowed.split(",") if h.strip()}
    assert {"content-type", "cache-control", "last-event-id"}.issubset(allowed_set)


@pytest.mark.asyncio
async def test_preflight_does_not_set_credentials(allowed_client) -> None:
    """``Access-Control-Allow-Credentials`` MUST NOT be present, so cookies
    do not flow cross-origin."""
    resp = await allowed_client.options(
        "/requests",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-credentials" not in {k.lower() for k in resp.headers.keys()}


@pytest.mark.asyncio
async def test_preflight_max_age_600_seconds(allowed_client) -> None:
    resp = await allowed_client.options(
        "/requests",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-max-age") == "600"


@pytest.mark.asyncio
async def test_empty_origins_list_installs_no_middleware() -> None:
    """Default settings (empty allow-list) → no CORS headers ever set."""
    settings = ServiceSettings(
        enable_chat_completions=False,
        lifecycle_sqlite_path=None,
        dashboard_origins=[],
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/requests", headers={"Origin": "http://127.0.0.1:5173"})
    assert "access-control-allow-origin" not in {k.lower() for k in resp.headers.keys()}


@pytest.mark.asyncio
async def test_post_returns_405_regardless_of_origin(allowed_client) -> None:
    """Read-only enforcement: mutation methods return 405 even from an
    allowed origin (CORS does not turn the route into a write surface)."""
    resp = await allowed_client.post(
        "/requests",
        headers={"Origin": "http://127.0.0.1:5173"},
    )
    assert resp.status_code == 405
