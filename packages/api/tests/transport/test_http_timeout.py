"""Pipeline calls exceeding ``request_timeout_seconds`` return HTTP 504.

Uses a stub pipeline whose ``pre_process`` sleeps far longer than the
configured timeout; asserts HTTP 504 with ``RefusalCode.API_TRANSPORT_TIMEOUT``
and an incremented ``arc_guardrails.api.timeout`` counter.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
from arc_guard_core.types import GuardInput, GuardResult

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


class _SlowPipeline:
    """Pipeline that sleeps before returning."""

    def __init__(self, sleep_seconds: float) -> None:
        self.sleep_seconds = sleep_seconds

    async def pre_process(self, input: GuardInput) -> GuardResult:
        await asyncio.sleep(self.sleep_seconds)
        return GuardResult(text=input.text, action="pass")


@pytest.mark.asyncio
async def test_slow_pipeline_returns_504() -> None:
    settings = ServiceSettings(request_timeout_seconds=0.1)
    app = create_app(settings, pipeline=_SlowPipeline(sleep_seconds=2.0))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=10.0,
    ) as client:
        response = await client.post("/v1/guard", json={"text": "slow"})

    assert response.status_code == 504
    body = response.json()
    assert body["code"] == "api_transport_timeout"

    metrics = app.state.arc_guard_metrics
    assert metrics["timeout"][0] >= 1


@pytest.mark.asyncio
async def test_fast_pipeline_does_not_increment_timeout_counter() -> None:
    settings = ServiceSettings(request_timeout_seconds=5.0)
    app = create_app(settings, pipeline=_SlowPipeline(sleep_seconds=0.01))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/guard", json={"text": "fast"})

    assert response.status_code == 200
    assert app.state.arc_guard_metrics["timeout"][0] == 0
