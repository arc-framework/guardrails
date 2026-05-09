"""Live-backend contract test: every corpus prompt's expected outcome.

Skipped entirely when OLLAMA_BASE_URL is not set, so CI without a backend
still runs the rest of the suite cleanly.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import httpx
import pytest

from arc_guard_service.examples_loader import CORPUS_DIR, CorpusPrompt, load_corpus
from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


def _backend_available() -> bool:
    return bool(os.environ.get("OLLAMA_BASE_URL"))


def _extra_installed(name: str) -> bool:
    if name == "jailbreak-ml":
        return importlib.util.find_spec("transformers") is not None
    if name == "semantic":
        return importlib.util.find_spec("sentence_transformers") is not None
    return False


_PROMPTS = load_corpus(CORPUS_DIR) if (CORPUS_DIR / "prompts").is_dir() else []


@pytest.fixture()
def settings(tmp_path: Path) -> ServiceSettings:
    base_url = os.environ["OLLAMA_BASE_URL"].rstrip("/")
    return ServiceSettings(
        backend="ollama",
        ollama_url=f"{base_url}/v1/chat/completions",
        lifecycle_sqlite_path=str(tmp_path / "arc_guardrail.db"),
    )


@pytest.fixture()
async def client(settings: ServiceSettings) -> httpx.AsyncClient:
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.skipif(not _backend_available(), reason="OLLAMA_BASE_URL not set")
@pytest.mark.asyncio
@pytest.mark.parametrize("prompt", _PROMPTS, ids=lambda p: p.id)
async def test_corpus_prompt_matches_expected_outcome(
    client: httpx.AsyncClient, prompt: CorpusPrompt
) -> None:
    if prompt.requires_extra and not _extra_installed(prompt.requires_extra):
        pytest.skip(f"Requires [{prompt.requires_extra}] extra")
    response = await client.post("/v1/chat/completions", json=prompt.request)
    assert response.status_code == 200, response.text
    arc_guard = response.json()["arc_guard"]
    phase_block = arc_guard[prompt.expected.phase]
    assert phase_block["action"] == prompt.expected.action, (
        f"{prompt.id}: expected action={prompt.expected.action}, got {phase_block['action']}"
    )
    expected_findings = set(prompt.expected.findings)
    actual_findings = set(phase_block.get("findings", []))
    if prompt.expected.tolerance == "strict":
        assert actual_findings == expected_findings, f"{prompt.id}: findings mismatch"
    else:
        assert expected_findings.issubset(actual_findings), f"{prompt.id}: findings subset failed"
    assert phase_block.get("refusal_code") == prompt.expected.refusal_code
