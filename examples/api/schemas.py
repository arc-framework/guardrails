"""Pydantic models for the OpenAI-compatible chat-completions surface.

Both the request and the response use ``model_config = ConfigDict(extra="allow")``
because the OpenAI API ecosystem is wide — clients send fields we don't model
(e.g. ``tools``, ``response_format``, ``logprobs``), and backends return fields
we don't model (e.g. ``system_fingerprint``, vendor extensions). Permissive
extras keep the api transparent — anything we don't validate, we forward.

The custom ``arc_guard`` field on the response carries per-request lifecycle
metadata that an OpenAI client would ignore but a dashboard reads.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ----- request side -----


class ChatMessage(BaseModel):
    """One message in the OpenAI chat conversation."""

    model_config = ConfigDict(extra="allow")

    role: Literal["system", "user", "assistant", "tool", "developer"] = Field(
        description="Sender role for this message."
    )
    content: str | None = Field(
        default=None,
        description="Message text. Optional for tool/assistant messages with tool_calls.",
    )
    name: str | None = Field(
        default=None,
        description="Optional sender name (OpenAI passes this for tool messages).",
    )


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request.

    Permissive: any unknown field is forwarded to the backend as-is.
    """

    model_config = ConfigDict(extra="allow")

    model: str = Field(description="Model id to invoke on the configured backend.")
    messages: list[ChatMessage] = Field(
        min_length=1,
        description="Conversation history, ordered oldest-first. Must contain at least one message; arc-guard inspects the LAST user message on the inbound side.",
    )
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    n: int | None = Field(default=None, ge=1)
    max_tokens: int | None = Field(default=None, ge=1)
    stream: bool | None = Field(
        default=None,
        description="Streaming is NOT yet supported by this api — set to false or omit.",
    )
    stop: str | list[str] | None = None
    presence_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    frequency_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    user: str | None = Field(
        default=None,
        description="Opaque end-user id; passed through to the backend if supplied.",
    )


# ----- response side -----


class ChatCompletionChoice(BaseModel):
    model_config = ConfigDict(extra="allow")

    index: int
    message: ChatMessage
    finish_reason: str | None = Field(
        default=None,
        description="`stop`, `length`, `content_filter` (arc-guard block), `tool_calls`, etc.",
    )


class ChatCompletionUsage(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ArcGuardPhase(BaseModel):
    """Per-phase metadata describing what arc-guard did at one boundary."""

    action: str = Field(
        description="One of `pass`, `block`, `redact`, `hash`, `tokenize`, `warn`."
    )
    findings: list[str] = Field(
        default_factory=list,
        description="Entity types fired by inspectors (e.g. `EMAIL_ADDRESS`, `INJECTION`, `JAILBREAK_DIRECT_OVERRIDE`).",
    )
    refusal_code: str | None = Field(
        default=None,
        description="Refusal code if the phase produced a refusal envelope (e.g. `jailbreak_strong`).",
    )
    sanitized: bool = Field(
        description="True when this phase mutated the text (redact / hash / tokenize), false for pass / block."
    )


class ArcGuardEnvelope(BaseModel):
    """Per-request lifecycle envelope. The dashboard reads this."""

    blocked: bool = Field(description="True when either phase produced a block.")
    blocked_phase: Literal["pre_process", "post_process"] | None = Field(
        default=None,
        description="Which phase blocked, if any.",
    )
    pre_process: ArcGuardPhase | None = Field(
        description="Inbound user-message phase. Always populated unless the request was rejected before guard ran."
    )
    post_process: ArcGuardPhase | None = Field(
        default=None,
        description="Outbound assistant-message phase. Null when pre_process blocked the request (the backend was never called).",
    )


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response, plus the arc_guard envelope."""

    model_config = ConfigDict(extra="allow")

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage = Field(default_factory=ChatCompletionUsage)
    arc_guard: ArcGuardEnvelope | None = Field(
        default=None,
        description="arc-guard per-request lifecycle metadata. Always populated by this api.",
    )


# ----- error envelope (kept for /docs) -----


class RefusalEnvelopeBody(BaseModel):
    """Shape of a 4xx/5xx error body returned when arc-guard or the transport blocks."""

    model_config = ConfigDict(extra="allow")

    code: str = Field(description="Refusal code, e.g. `api_invalid_request`.")
    trigger: str
    policy: str | None = None
    human_message: str
    next_steps: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ----- root descriptor -----


class ServiceDescriptor(BaseModel):
    """What `GET /` returns — a tiny health/identity payload."""

    service: str
    backend: str
    endpoint: str


__all__ = [
    "ChatMessage",
    "ChatCompletionRequest",
    "ChatCompletionChoice",
    "ChatCompletionUsage",
    "ChatCompletionResponse",
    "ArcGuardPhase",
    "ArcGuardEnvelope",
    "RefusalEnvelopeBody",
    "ServiceDescriptor",
]
