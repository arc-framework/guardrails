"""Corpus-backed chat preset manifest for dashboard chat surfaces.

Exposes ``GET /chat/examples`` so the dashboard can populate its preset
picker from the same validated corpus that feeds the OpenAPI request-body
examples on ``POST /v1/chat/completions``.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from arc_guard_service.examples_loader import CORPUS_DIR, CorpusError, load_corpus
from arc_guard_service.schemas import ChatCompletionRequest, ChatExamplePreset

_LOG = logging.getLogger("arc_guard.chat_examples")


def _last_user_prompt(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content")
            return content if isinstance(content, str) else ""
    return ""


def build_chat_examples_router() -> Any:
    """Construct a FastAPI router exposing ``GET /chat/examples``."""

    fastapi = importlib.import_module("fastapi")
    APIRouter = fastapi.APIRouter  # noqa: N806
    HTTPException = fastapi.HTTPException  # noqa: N806

    router = APIRouter()

    @router.get(
        "/chat/examples",
        response_model=list[ChatExamplePreset],
        summary="Validated chat presets sourced from the Swagger/OpenAPI corpus",
        tags=["chat"],
    )
    async def list_chat_examples() -> list[ChatExamplePreset]:
        prompts_dir = CORPUS_DIR / "prompts"
        if not prompts_dir.is_dir():
            return []
        try:
            prompts = load_corpus(CORPUS_DIR)
        except CorpusError as exc:
            _LOG.warning("chat examples corpus invalid: %s", exc)
            raise HTTPException(
                status_code=500,
                detail={
                    "error": {
                        "code": "corpus_invalid",
                        "message": f"chat examples corpus invalid: {exc}",
                    }
                },
            ) from exc

        presets: list[ChatExamplePreset] = []
        for prompt in prompts:
            request = ChatCompletionRequest.model_validate(prompt.request)
            raw_messages = [message.model_dump(exclude_none=True) for message in request.messages]
            presets.append(
                ChatExamplePreset(
                    id=prompt.id,
                    inspector=prompt.inspector,
                    difficulty=prompt.difficulty,
                    summary=prompt.swagger_summary,
                    description=prompt.swagger_description,
                    model=request.model,
                    messages=request.messages,
                    user_prompt=_last_user_prompt(raw_messages),
                    message_count=len(request.messages),
                    tags=prompt.tags,
                    expected_action=prompt.expected.action,
                    expected_phase=prompt.expected.phase,
                    refusal_code=prompt.expected.refusal_code,
                )
            )
        return presets

    return router