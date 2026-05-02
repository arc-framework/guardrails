"""Bodies larger than ``max_request_bytes`` return HTTP 413 + refusal envelope.

Configures the service with a small ``max_request_bytes`` and posts a body
that exceeds the limit; asserts HTTP 413 and the structured envelope.
"""

from __future__ import annotations

import httpx
import pytest

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


@pytest.mark.asyncio
async def test_body_above_limit_returns_413() -> None:
    settings = ServiceSettings(max_request_bytes=1024)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    big_text = "x" * 4096
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/guard", json={"text": big_text})

    assert response.status_code == 413
    body = response.json()
    assert body["code"] == "api_invalid_request"
    assert body["human_message"]


@pytest.mark.asyncio
async def test_body_at_limit_succeeds() -> None:
    settings = ServiceSettings(max_request_bytes=4096)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    body = {"text": "x" * 100}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/guard", json=body)
    assert response.status_code == 200
