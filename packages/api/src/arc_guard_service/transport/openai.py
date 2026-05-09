"""OpenAI-compatible chat-completions transport for arc-guard-service.

Mounts ``POST /v1/chat/completions`` onto a FastAPI app. Every request is
intercepted twice: ``GuardPipeline.pre_process`` on the inbound user
message and ``GuardPipeline.post_process`` on the assistant response.

Backend selection is driven by ``ServiceSettings.backend``:

- ``echo``   — no LLM; fake backend echoes the (possibly sanitized) text.
- ``ollama`` — forwards to ``ServiceSettings.ollama_url``.
- ``openai`` — forwards to ``ServiceSettings.openai_url`` with bearer auth.

A blocked verdict at either phase returns an OpenAI-shaped response with
``finish_reason='content_filter'`` and the refusal envelope's
``human_message`` as the assistant content. The custom ``arc_guard``
field on every response carries per-phase metadata for dashboards.

This module is import-safe without the ``[fastapi]`` extra: the FastAPI
imports happen inside ``build_router``.

Like ``transport.http``, this module avoids ``from __future__ import
annotations`` so FastAPI's runtime introspection works on the route
parameter annotations.
"""

import importlib
import logging
import time
import uuid
from typing import Any

from arc_guard_core.lifecycle import (
    BackendCalled,
    BackendResponded,
    LifecycleEmitter,
    LifecycleSink,
    NullLifecycleSink,
    NullPayloadCapturePolicy,
    PayloadCapturePolicy,
    PayloadRewritten,
    PostProcessCompleted,
    PostProcessStarted,
    PreProcessCompleted,
    PreProcessStarted,
    RequestCompleted,
    RequestStarted,
    ResponseAssembled,
)
from arc_guard_core.types import GuardContext, GuardInput

from arc_guard_service.examples_loader import (
    OPENAPI_EXAMPLES as _REQUEST_EXAMPLES,
)
from arc_guard_service.schemas import (
    ArcGuardEnvelope,
    ArcGuardPhase,
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionUsage,
    ChatMessage,
    RefusalEnvelopeBody,
)
from arc_guard_service.settings import ServiceSettings

_LOG = logging.getLogger("arc-guard.api.openai")


def _phase_meta(result: Any) -> ArcGuardPhase:
    return ArcGuardPhase(
        action=result.action,
        findings=[f.entity_type for f in result.findings],
        refusal_code=result.refusal.code if result.refusal is not None else None,
        sanitized=result.action not in ("pass", "block"),
    )


# Forbidden substrings (case-insensitive) for the model-config scrubber.
# Any payload key matching ANY of these is dropped before assignment to the
# BackendCalled.model_config_snapshot field.
_FORBIDDEN_KEY_SUBSTRINGS = ("key", "secret", "token", "auth", "password")


def _scrub_forbidden_keys(d: dict) -> dict:
    """Drop any dict entry whose key contains a forbidden substring.

    Comparison is case-insensitive. Returns a new dict; the input is not
    mutated. Used by the model-config snapshot to keep credentials off
    lifecycle events.
    """
    out: dict = {}
    for k, v in d.items():
        kl = str(k).lower()
        if any(s in kl for s in _FORBIDDEN_KEY_SUBSTRINGS):
            continue
        out[k] = v
    return out


def _build_model_config_snapshot(
    *, provider: str, payload: dict
) -> dict[str, str | int | float] | None:
    """Build the bounded snapshot dict for BackendCalled.model_config_snapshot.

    Returns the four documented keys (provider, model, temperature,
    max_tokens) when at least one is available; returns None when no
    field could be populated.

    The whitelist approach is the primary safety mechanism: only the four
    permitted keys are ever copied from the payload, so credentials in
    other fields can never end up in the snapshot. The
    ``_scrub_forbidden_keys`` helper exists as a separate utility for
    ad-hoc dicts where the keys are not known statically.
    """
    snapshot: dict[str, str | int | float] = {"provider": provider}
    model = payload.get("model") if isinstance(payload, dict) else None
    if isinstance(model, str):
        snapshot["model"] = model
    temperature = payload.get("temperature") if isinstance(payload, dict) else None
    if isinstance(temperature, (int, float)) and not isinstance(temperature, bool):
        snapshot["temperature"] = float(temperature)
    max_tokens = payload.get("max_tokens") if isinstance(payload, dict) else None
    if isinstance(max_tokens, int) and not isinstance(max_tokens, bool):
        snapshot["max_tokens"] = max_tokens
    return snapshot if snapshot else None


def _extract_token_usage(
    response: dict,
) -> dict[str, int] | None:
    """Pull the OpenAI-shaped ``usage`` object out of a backend response.

    Returns a dict containing the three documented keys when ``usage`` is
    a dict in the response; returns None otherwise. Each key defaults to
    0 if the backend reported it missing or non-integer.
    """
    if not isinstance(response, dict):
        return None
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return None
    out: dict[str, int] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        v = usage.get(key, 0)
        out[key] = v if isinstance(v, int) and not isinstance(v, bool) else 0
    return out


def _refusal_response(
    *,
    model: str,
    content: str,
    arc_guard: ArcGuardEnvelope,
    response_id: str,
) -> ChatCompletionResponse:
    return ChatCompletionResponse(
        id=response_id,
        object="chat.completion",
        created=int(time.time()),
        model=model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=content),
                finish_reason="content_filter",
            )
        ],
        usage=ChatCompletionUsage(),
        arc_guard=arc_guard,
    )


# Per-request emitter is provided by `arc_guard_core.lifecycle.LifecycleEmitter`.
# We keep the `_RidEmitter` name as a local alias so older diffs read cleanly,
# but it's the same class — and crucially, the pipeline imports the same class
# via `arc_guard_core.lifecycle.LifecycleEmitter`, so api transport events and
# pipeline-internal events share one seq counter per rid.
_RidEmitter = LifecycleEmitter


def build_router(
    *,
    settings: ServiceSettings,
    pipeline: Any,
    http_client: Any,
    lifecycle_sink: LifecycleSink | None = None,
    payload_capture_policy: PayloadCapturePolicy | None = None,
) -> Any:
    """Build the FastAPI router carrying ``POST /v1/chat/completions``.

    ``http_client`` must be an httpx.AsyncClient compatible object; the
    router shares it across requests for connection pooling.

    ``lifecycle_sink`` receives transport-layer lifecycle events
    (``RequestStarted`` … ``RequestCompleted`` plus ``BackendCalled`` /
    ``BackendResponded`` / ``PayloadRewritten`` / ``ResponseAssembled``).
    Defaults to ``NullLifecycleSink`` so callers that don't opt in see no
    behavior change.

    ``payload_capture_policy`` decides whether richer payload fields
    (``RequestStarted.raw_input``, ``BackendResponded.response_text``,
    ``SanitizationApplied.text_after``) are populated. Defaults to
    ``NullPayloadCapturePolicy`` (capture nothing).
    """
    fastapi = importlib.import_module("fastapi")
    sink: LifecycleSink = lifecycle_sink or NullLifecycleSink()
    capture_policy: PayloadCapturePolicy = payload_capture_policy or NullPayloadCapturePolicy()

    Body = fastapi.Body  # noqa: N806
    HTTPException = fastapi.HTTPException  # noqa: N806
    Request = fastapi.Request  # noqa: N806
    APIRouter = fastapi.APIRouter  # noqa: N806

    router = APIRouter()

    async def _call_backend(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Returns (response_body, http_status). Echo backend reports 200."""
        if settings.backend == "echo":
            last_user = next(
                (
                    m.get("content", "")
                    for m in reversed(payload.get("messages", []))
                    if m.get("role") == "user"
                ),
                "",
            )
            return (
                {
                    "id": "chatcmpl-echo",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": payload.get("model", "echo"),
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": f"[echo backend] I would respond to: {last_user}",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                    },
                },
                200,
            )

        if settings.backend == "ollama":
            resp = await http_client.post(settings.ollama_url, json=payload)
            resp.raise_for_status()
            return resp.json(), resp.status_code

        if settings.backend == "openai":
            if not settings.openai_api_key:
                raise HTTPException(500, "openai_api_key not set; cannot use backend=openai")
            resp = await http_client.post(
                settings.openai_url,
                json=payload,
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            )
            resp.raise_for_status()
            return resp.json(), resp.status_code

        raise HTTPException(500, f"unknown backend: {settings.backend!r}")

    @router.post(
        "/v1/chat/completions",
        response_model=ChatCompletionResponse,
        response_model_exclude_none=False,
        summary="OpenAI-compatible chat completion with arc-guard pre/post intercept",
        tags=["chat"],
        responses={
            400: {"model": RefusalEnvelopeBody, "description": "Malformed request."},
            413: {"model": RefusalEnvelopeBody, "description": "Request body too large."},
            502: {
                "model": RefusalEnvelopeBody,
                "description": "Backend returned malformed response.",
            },
            504: {"model": RefusalEnvelopeBody, "description": "Backend timeout."},
        },
    )
    async def chat_completions(  # type: ignore[no-untyped-def]
        request: ChatCompletionRequest = Body(openapi_examples=_REQUEST_EXAMPLES),
        http_request: Request = None,  # type: ignore[assignment]
    ) -> ChatCompletionResponse:
        from arc_guard_service.transport._rid import resolve_rid

        rid = resolve_rid(http_request)
        started = time.perf_counter()
        emitter = _RidEmitter(sink, rid, policy=capture_policy)

        user_messages = [m for m in request.messages if m.role == "user"]
        if not user_messages:
            _LOG.warning("[rid=%s] rejected: no user message in conversation", rid)
            raise HTTPException(400, "no user message in conversation")

        last_user = user_messages[-1]
        user_text = last_user.content or ""
        _LOG.info(
            "[rid=%s] request: model=%s msgs=%d last_user_chars=%d",
            rid,
            request.model,
            len(request.messages),
            len(user_text),
        )

        # === RequestStarted (root) ===
        # raw_input is populated only when the policy explicitly opts in.
        # Documented as security-sensitive; default policy never enables.
        request_started = await emitter.emit(
            RequestStarted,
            parent_id=None,
            route="/v1/chat/completions",
            model=request.model,
            msg_count=len(request.messages),
            input_size_bytes=len(user_text),
            raw_input=user_text if emitter.policy.should_capture_raw_input() else None,
        )
        root_id = request_started.id

        # === PreProcessStarted → pre_process → PreProcessCompleted ===
        # Pre-generate the correlation_id so we can carry it on PreProcessStarted
        # and the pipeline picks up the same id from GuardContext.correlation_id.
        pre_correlation_id = uuid.uuid4().hex
        pre_started = await emitter.emit(
            PreProcessStarted,
            parent_id=root_id,
            correlation_id=pre_correlation_id,
            decision_id="",
        )
        pre_phase_t0 = time.perf_counter()
        # Pass the lifecycle emitter + the parent (PreProcessStarted.id) into
        # the pipeline via context metadata so pipeline-internal events
        # (StageRan, InspectorRan, FindingProduced, etc.) share the same rid +
        # seq counter as the transport events. Default-off when the api isn't
        # wired (SDK-only callers won't populate this).
        pre_result = await pipeline.pre_process(
            GuardInput(
                text=user_text,
                context=GuardContext(
                    correlation_id=pre_correlation_id,
                    metadata={
                        "_lifecycle_emitter": emitter,
                        "_lifecycle_parent_id": pre_started.id,
                    },
                ),
            )
        )
        pre_meta = _phase_meta(pre_result)
        _LOG.info(
            "[rid=%s] pre_process: action=%s sanitized=%s findings=%s",
            rid,
            pre_meta.action,
            pre_meta.sanitized,
            pre_meta.findings or "[]",
        )
        await emitter.emit(
            PreProcessCompleted,
            parent_id=pre_started.id,
            action=pre_meta.action,
            blocked=(pre_result.action == "block"),
            total_duration_ms=(time.perf_counter() - pre_phase_t0) * 1000,
        )

        if pre_result.action == "block":
            refusal_text = (
                pre_result.refusal.human_message
                if pre_result.refusal is not None
                else "Request blocked by guard."
            )
            _LOG.warning(
                "[rid=%s] BLOCKED at pre_process: refusal_code=%s findings=%s elapsed_ms=%.1f",
                rid,
                pre_meta.refusal_code,
                pre_meta.findings,
                (time.perf_counter() - started) * 1000,
            )
            await emitter.emit(
                ResponseAssembled,
                parent_id=root_id,
                response_id="chatcmpl-arcguard-blocked-input",
                finish_reason="content_filter",
                arc_guard_blocked=True,
                response_text=(refusal_text if emitter.policy.should_capture_sanitized() else None),
            )
            await emitter.emit(
                RequestCompleted,
                parent_id=root_id,
                blocked=True,
                pre_action=pre_meta.action,
                post_action=None,
                total_duration_ms=(time.perf_counter() - started) * 1000,
            )
            return _refusal_response(
                model=request.model,
                content=refusal_text,
                arc_guard=ArcGuardEnvelope(
                    blocked=True,
                    blocked_phase="pre_process",
                    pre_process=pre_meta,
                    post_process=None,
                    rid=rid,
                ),
                response_id="chatcmpl-arcguard-blocked-input",
            )

        payload = request.model_dump(exclude_none=True)
        payload_rewritten_id: str | None = None
        if pre_result.action != "pass":
            # Find the last user-message slot before mutating so we can record
            # the pre/post sizes for the PayloadRewritten event.
            target_msg = next(
                (m for m in reversed(payload["messages"]) if m.get("role") == "user"),
                None,
            )
            if target_msg is not None:
                before_text = target_msg.get("content", "") or ""
                before_size = len(before_text)
                target_msg["content"] = pre_result.text
                pr_event = await emitter.emit(
                    PayloadRewritten,
                    parent_id=root_id,
                    message_index=payload["messages"].index(target_msg),
                    field="content",
                    before_size=before_size,
                    after_size=len(pre_result.text or ""),
                    text_before=(
                        (
                            before_text
                            if emitter.policy.should_capture_raw_input()
                            else pre_result.text
                        )
                        if emitter.policy.should_capture_sanitized()
                        else None
                    ),
                    text_after=(
                        pre_result.text if emitter.policy.should_capture_sanitized() else None
                    ),
                )
                payload_rewritten_id = pr_event.id

        _LOG.info(
            "[rid=%s] backend(%s): forwarding %d messages",
            rid,
            settings.backend,
            len(payload["messages"]),
        )
        # Build a bounded model-config snapshot for the dashboard. Only the
        # four documented keys ship; anything resembling a credential is
        # scrubbed before assignment by _build_model_config_snapshot.
        model_config_snapshot = _build_model_config_snapshot(
            provider=settings.backend, payload=payload
        )
        backend_called = await emitter.emit(
            BackendCalled,
            parent_id=root_id,
            backend=settings.backend,
            url=(
                "echo://local"
                if settings.backend == "echo"
                else (settings.ollama_url if settings.backend == "ollama" else settings.openai_url)
            ),
            payload_msg_count=len(payload["messages"]),
            model_config_snapshot=model_config_snapshot,
        )
        backend_started_t0 = time.perf_counter()
        backend_response, backend_http_status = await _call_backend(payload)
        _LOG.info(
            "[rid=%s] backend(%s): returned in %.1f ms (http=%d)",
            rid,
            settings.backend,
            (time.perf_counter() - backend_started_t0) * 1000,
            backend_http_status,
        )

        try:
            choices = backend_response["choices"]
            assistant_msg = choices[0]["message"]
            assistant_text = assistant_msg.get("content", "") or ""
            backend_finish_reason = choices[0].get("finish_reason")
        except (KeyError, IndexError, TypeError) as exc:
            _LOG.error("[rid=%s] backend returned malformed response: %s", rid, exc)
            raise HTTPException(502, f"backend returned malformed response: {exc}") from exc

        # Token usage is reported by OpenAI-compatible backends in the
        # ``usage`` response field. Echo backend emits no usage. We only
        # ship the three documented keys; missing values default to 0.
        token_usage = _extract_token_usage(backend_response)
        await emitter.emit(
            BackendResponded,
            parent_id=backend_called.id,
            duration_ms=(time.perf_counter() - backend_started_t0) * 1000,
            http_status=backend_http_status,
            response_msg_chars=len(assistant_text),
            response_finish_reason=backend_finish_reason,
            swap_origin_id=payload_rewritten_id,
            response_text=(assistant_text if emitter.policy.should_capture_sanitized() else None),
            token_usage=token_usage,
        )

        # === PostProcessStarted → post_process → PostProcessCompleted ===
        post_correlation_id = uuid.uuid4().hex
        post_started = await emitter.emit(
            PostProcessStarted,
            parent_id=root_id,
            correlation_id=post_correlation_id,
            decision_id="",
        )
        post_phase_t0 = time.perf_counter()
        post_result = await pipeline.post_process(
            GuardInput(
                text=assistant_text,
                context=GuardContext(
                    correlation_id=post_correlation_id,
                    metadata={
                        "_lifecycle_emitter": emitter,
                        "_lifecycle_parent_id": post_started.id,
                    },
                ),
            )
        )
        post_meta = _phase_meta(post_result)
        _LOG.info(
            "[rid=%s] post_process: action=%s sanitized=%s findings=%s",
            rid,
            post_meta.action,
            post_meta.sanitized,
            post_meta.findings or "[]",
        )
        await emitter.emit(
            PostProcessCompleted,
            parent_id=post_started.id,
            action=post_meta.action,
            blocked=(post_result.action == "block"),
            total_duration_ms=(time.perf_counter() - post_phase_t0) * 1000,
        )

        if post_result.action == "block":
            refusal_text = (
                post_result.refusal.human_message
                if post_result.refusal is not None
                else "Response blocked by guard."
            )
            backend_response["choices"][0]["message"]["content"] = refusal_text
            backend_response["choices"][0]["finish_reason"] = "content_filter"
            backend_response["arc_guard"] = ArcGuardEnvelope(
                blocked=True,
                blocked_phase="post_process",
                pre_process=pre_meta,
                post_process=post_meta,
                rid=rid,
            ).model_dump()
            _LOG.warning(
                "[rid=%s] BLOCKED at post_process: refusal_code=%s findings=%s elapsed_ms=%.1f",
                rid,
                post_meta.refusal_code,
                post_meta.findings,
                (time.perf_counter() - started) * 1000,
            )
            await emitter.emit(
                ResponseAssembled,
                parent_id=root_id,
                response_id=str(backend_response.get("id", "")),
                finish_reason="content_filter",
                arc_guard_blocked=True,
                response_text=(
                    assistant_text if emitter.policy.should_capture_sanitized() else None
                ),
            )
            await emitter.emit(
                RequestCompleted,
                parent_id=root_id,
                blocked=True,
                pre_action=pre_meta.action,
                post_action=post_meta.action,
                total_duration_ms=(time.perf_counter() - started) * 1000,
            )
            return ChatCompletionResponse.model_validate(backend_response)

        if post_result.action != "pass":
            backend_response["choices"][0]["message"]["content"] = post_result.text

        backend_response["arc_guard"] = ArcGuardEnvelope(
            blocked=False,
            blocked_phase=None,
            pre_process=pre_meta,
            post_process=post_meta,
            rid=rid,
        ).model_dump()
        _LOG.info(
            "[rid=%s] response: ok elapsed_ms=%.1f",
            rid,
            (time.perf_counter() - started) * 1000,
        )
        # The text the API ultimately returns to the caller is whichever
        # post_result produced. When post_process did not modify the
        # assistant's reply, post_result.text matches assistant_text.
        final_assistant_text = post_result.text or assistant_text
        await emitter.emit(
            ResponseAssembled,
            parent_id=root_id,
            response_id=str(backend_response.get("id", "")),
            finish_reason=str(backend_response["choices"][0].get("finish_reason", "stop")),
            arc_guard_blocked=False,
            response_text=(
                final_assistant_text if emitter.policy.should_capture_sanitized() else None
            ),
        )
        await emitter.emit(
            RequestCompleted,
            parent_id=root_id,
            blocked=False,
            pre_action=pre_meta.action,
            post_action=post_meta.action,
            total_duration_ms=(time.perf_counter() - started) * 1000,
        )
        return ChatCompletionResponse.model_validate(backend_response)

    return router


__all__ = ["build_router"]
