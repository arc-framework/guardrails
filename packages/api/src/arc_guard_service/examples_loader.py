"""Corpus loader for OpenAPI request-body examples.

Reads YAML prompts from ``packages/api/tests/corpus/prompts/``, validates
them against a Pydantic schema (with cross-rules), and exposes them as
the ``OPENAPI_EXAMPLES`` dict consumed by ``transport/openai.py``.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from arc_guard_service.schemas.openai import ChatCompletionRequest


class ExpectedOutcome(BaseModel):
    action: Literal["pass", "redact", "tokenize", "hash", "block"]
    phase: Literal["pre_process", "post_process"]
    refusal_code: str | None = None
    findings: list[str] = Field(default_factory=list)
    tolerance: Literal["strict", "subset"] | None = None
    false_positive: bool = False

    @model_validator(mode="after")
    def _refusal_code_iff_block(self) -> "ExpectedOutcome":
        if self.action == "block" and self.refusal_code is None:
            raise ValueError("refusal_code must be set when action == 'block'")
        if self.action != "block" and self.refusal_code is not None:
            raise ValueError("refusal_code must be null when action != 'block'")
        return self

    @model_validator(mode="after")
    def _default_tolerance(self) -> "ExpectedOutcome":
        if self.tolerance is None:
            object.__setattr__(
                self,
                "tolerance",
                "strict" if self.phase == "pre_process" else "subset",
            )
        return self


class CorpusPrompt(BaseModel):
    id: str
    inspector: str
    difficulty: Literal["easy", "medium", "super_hard"]
    swagger_summary: str
    swagger_description: str
    request: dict[str, Any]
    expected: ExpectedOutcome
    requires_extra: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    references: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _request_round_trips(self) -> "CorpusPrompt":
        try:
            ChatCompletionRequest.model_validate(self.request)
        except Exception as exc:
            raise ValueError(f"request does not validate as ChatCompletionRequest: {exc}") from exc
        return self
