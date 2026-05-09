"""Malformed request bodies produce HTTP 400 + structured refusal envelope.

Asserts no raw exception text leaks into the response body — the
``human_message`` is the registered refusal-template message, not
``str(exc)``.
"""

from __future__ import annotations

import httpx
import pytest

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


@pytest.mark.asyncio
async def test_invalid_json_returns_400_with_envelope() -> None:
    app = create_app(ServiceSettings())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/guard",
            content="not json",
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "api_invalid_request"
    assert body["human_message"]
    assert "stub" not in body["human_message"]


@pytest.mark.asyncio
async def test_missing_text_returns_400_with_envelope() -> None:
    app = create_app(ServiceSettings())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/guard", json={})
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "api_invalid_request"
    assert body["next_steps"]


@pytest.mark.asyncio
async def test_wrong_text_type_returns_400_with_envelope() -> None:
    app = create_app(ServiceSettings())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/guard", json={"text": 12345})
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "api_invalid_request"


@pytest.mark.asyncio
async def test_no_raw_exception_text_in_response_body() -> None:
    app = create_app(ServiceSettings())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/guard",
            content="{not even valid json",
            headers={"content-type": "application/json"},
        )
    body = response.json()
    text_blob = " ".join(str(v) for v in body.values())
    assert "Traceback" not in text_blob
    assert "JSONDecodeError" not in text_blob
