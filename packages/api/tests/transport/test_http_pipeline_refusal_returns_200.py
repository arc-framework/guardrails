"""Pipeline-produced refusals (normal ``result.action == "block"``) return HTTP 200.

Distinguishes transport-layer rejection (4xx/5xx) from guard-decision
rejection (200 with ``GuardResult.action == "block"``). Operators consume
``result.action`` and ``result.refusal`` for guard decisions; HTTP status
indicates transport health only.
"""

from __future__ import annotations

import httpx
import pytest
from arc_guard_core.types import GuardInput, GuardResult, RefusalEnvelope

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


class _RefusingPipeline:
    """Pipeline that always returns a block-action result."""

    async def pre_process(self, input: GuardInput) -> GuardResult:
        return GuardResult(
            text="",
            action="block",
            refusal=RefusalEnvelope(
                code="jailbreak_strong",
                trigger="jailbreak.detected",
                policy="rule-based:1",
                human_message="blocked by stub",
                next_steps=("rephrase",),
            ),
        )


@pytest.mark.asyncio
async def test_block_action_returns_200_not_4xx() -> None:
    app = create_app(ServiceSettings(), pipeline=_RefusingPipeline())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/guard", json={"text": "anything"})

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "block"
    assert body["refusal"]["code"] == "jailbreak_strong"
