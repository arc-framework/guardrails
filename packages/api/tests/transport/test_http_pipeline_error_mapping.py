"""``PipelineError`` subclasses map to HTTP statuses per the FAIL_RULE table.

Stub pipelines raise specific ``PipelineError`` subclasses; the test
asserts each maps to the documented HTTP status with the structured
refusal envelope.
"""

from __future__ import annotations

import httpx
import pytest
from arc_guard_core.exceptions import (
    InspectorError,
    PolicyRouterError,
    StrategyError,
    TransportError,
)
from arc_guard_core.types import GuardInput, GuardResult

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


class _RaisingPipeline:
    def __init__(self, exc: BaseException) -> None:
        self.exc = exc

    async def pre_process(self, input: GuardInput) -> GuardResult:
        raise self.exc


@pytest.mark.asyncio
async def test_inspector_error_maps_to_422() -> None:
    exc = InspectorError("boom", code="inspector.unhandled")
    app = create_app(ServiceSettings(), pipeline=_RaisingPipeline(exc))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/guard", json={"text": "x"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_strategy_error_maps_to_500() -> None:
    exc = StrategyError("boom", code="strategy.failed")
    app = create_app(ServiceSettings(), pipeline=_RaisingPipeline(exc))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/guard", json={"text": "x"})
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "strategy_failed"


@pytest.mark.asyncio
async def test_policy_router_error_maps_to_500() -> None:
    exc = PolicyRouterError("boom", code="router.no_decision")
    app = create_app(ServiceSettings(), pipeline=_RaisingPipeline(exc))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/guard", json={"text": "x"})
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "policy_block"


@pytest.mark.asyncio
async def test_transport_error_maps_to_504() -> None:
    exc = TransportError("boom", code="transport.timeout")
    app = create_app(ServiceSettings(), pipeline=_RaisingPipeline(exc))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/guard", json={"text": "x"})
    assert response.status_code == 504
    body = response.json()
    assert body["code"] == "api_transport_timeout"
