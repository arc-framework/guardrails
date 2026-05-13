"""Contract: ``/openapi.json`` chat-completions request examples come from the corpus.

The dropdown of example requests on the swagger UI for
``POST /v1/chat/completions`` must be sourced from the corpus loader, not
a hardcoded literal. This test asserts the published openapi schema
contains both a ``_baseline__`` example and at least one real-difficulty
example, which is only true when the loader is wired in.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


@pytest.fixture()
def settings(tmp_path: Path) -> ServiceSettings:
    return ServiceSettings(
        backend="echo",
        lifecycle_sqlite_path=str(tmp_path / "arc_guardrail.db"),
    )


@pytest.fixture()
async def client(settings: ServiceSettings) -> httpx.AsyncClient:
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_openapi_dropdown_is_sourced_from_corpus(
    client: httpx.AsyncClient,
) -> None:
    schema = (await client.get("/openapi.json")).json()
    body = schema["paths"]["/v1/chat/completions"]["post"]["requestBody"]
    examples = body["content"]["application/json"]["examples"]
    assert any(k.startswith("_baseline__") for k in examples)
    assert any("__easy__" in k or "__medium__" in k or "__super_hard__" in k for k in examples)
