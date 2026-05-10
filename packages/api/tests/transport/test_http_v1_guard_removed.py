"""``POST /v1/guard`` is a tombstone — every request returns 410 Gone
with the documented removal envelope pointing at the replacement
endpoint.

Tombstone is wired with ``api_route(..., methods=[POST,GET,PUT,...])``
so legacy callers see the same envelope regardless of HTTP verb.
"""

from __future__ import annotations

import httpx
import pytest

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


@pytest.mark.asyncio
async def test_post_v1_guard_returns_410_with_replacement_envelope() -> None:
    app = create_app(ServiceSettings())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/guard", json={"text": "anything"})
    assert response.status_code == 410, response.text
    body = response.json()
    assert body["error"]["code"] == "endpoint_removed"
    assert "/v1/chat/completions" in body["error"]["message"]
    assert body["error"]["replacement"] == "/v1/chat/completions"
    assert body["error"]["retired_in_spec"] == "014-pipeline-instrumentation-completion"


@pytest.mark.asyncio
async def test_post_v1_guard_returns_410_with_empty_body() -> None:
    """Tombstone returns the envelope even when callers send no body."""
    app = create_app(ServiceSettings())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/guard")
    assert response.status_code == 410
    assert response.json()["error"]["code"] == "endpoint_removed"


@pytest.mark.asyncio
async def test_get_v1_guard_returns_410_too() -> None:
    """Legacy callers using GET / curl-without-data also see the tombstone."""
    app = create_app(ServiceSettings())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/guard")
    assert response.status_code == 410
    assert response.json()["error"]["replacement"] == "/v1/chat/completions"


@pytest.mark.asyncio
async def test_root_descriptor_omits_v1_guard() -> None:
    """The service descriptor at ``GET /`` no longer advertises ``/v1/guard``."""
    app = create_app(ServiceSettings())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    endpoints = response.json()["endpoints"]
    assert all("/v1/guard" not in ep for ep in endpoints), endpoints


@pytest.mark.asyncio
async def test_openapi_omits_v1_guard() -> None:
    """Swagger/OpenAPI should not advertise the retired tombstone route."""
    app = create_app(ServiceSettings())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "/v1/guard" not in schema.get("paths", {}), schema.get("paths", {})
