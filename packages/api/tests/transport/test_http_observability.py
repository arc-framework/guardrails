"""HTTP transport increments the documented metrics per request.

The transport adds three metrics: ``arc_guardrails.api.requests_total``
(counter), ``arc_guardrails.api.timeout`` (counter), and
``arc_guardrails.api.duration`` (histogram). The transport-level state
holder tracks call counts so tests can assert metric semantics without
wiring a full OTEL backend.
"""

from __future__ import annotations

import httpx
import pytest

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


@pytest.mark.asyncio
async def test_requests_total_increments_per_request() -> None:
    app = create_app(ServiceSettings())
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/v1/guard", json={"text": "one"})
        await client.post("/v1/guard", json={"text": "two"})
        await client.post("/v1/guard", json={"text": "three"})

    metrics = app.state.arc_guard_metrics
    assert metrics["requests_total"][0] == 3


@pytest.mark.asyncio
async def test_duration_samples_recorded() -> None:
    app = create_app(ServiceSettings())
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/v1/guard", json={"text": "hello"})

    metrics = app.state.arc_guard_metrics
    assert len(metrics["duration"]) == 1
    assert metrics["duration"][0] >= 0.0
