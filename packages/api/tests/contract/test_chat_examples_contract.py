"""Contract: ``GET /chat/examples`` mirrors the validated corpus examples.

The dashboard uses this route to populate its chat preset picker, so it must
stay aligned with the same corpus that Swagger reads for request-body examples.
"""

from __future__ import annotations

import httpx
import pytest

from arc_guard_service.schemas import ChatExamplePreset
from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


@pytest.fixture()
async def client() -> httpx.AsyncClient:
    app = create_app(ServiceSettings(backend="echo"))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_examples_endpoint_returns_validated_presets(client: httpx.AsyncClient) -> None:
    response = await client.get("/chat/examples")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) > 0

    first = ChatExamplePreset.model_validate(body[0])
    assert first.id == "_baseline__multi_turn__01"
    assert first.message_count == len(first.messages)
    assert first.user_prompt == "And what about phone numbers like 555-0101?"


@pytest.mark.asyncio
async def test_examples_endpoint_exposes_expected_guard_metadata(client: httpx.AsyncClient) -> None:
    response = await client.get("/chat/examples")

    assert response.status_code == 200
    by_id = {item["id"]: item for item in response.json()}
    blocked = ChatExamplePreset.model_validate(by_id["prompt_injection__easy__03"])

    assert blocked.expected_action == "block"
    assert blocked.expected_phase == "pre_process"
    assert blocked.refusal_code == "jailbreak_strong"