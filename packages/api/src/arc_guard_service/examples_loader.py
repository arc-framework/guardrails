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


from pathlib import Path

import yaml


class CorpusError(Exception):
    """Raised when the corpus is malformed. Carries file path in message."""


def load_corpus(corpus_dir: Path) -> list[CorpusPrompt]:
    """Load and validate all YAML prompts under ``corpus_dir/prompts/``.

    Fail-fast: a single malformed file raises ``CorpusError`` and the
    whole corpus fails to load. The error message always includes the
    offending file path so authors can find it without grepping.
    """
    prompts_dir = corpus_dir / "prompts"
    if not prompts_dir.is_dir():
        raise CorpusError(f"corpus prompts directory missing: {prompts_dir}")
    prompts: list[CorpusPrompt] = []
    for path in sorted(prompts_dir.glob("*.yaml")):
        if path.is_symlink():
            raise CorpusError(f"symlinks not allowed in corpus: {path}")
        try:
            data = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            raise CorpusError(f"{path.name}: invalid YAML: {exc}") from exc
        try:
            prompt = CorpusPrompt.model_validate(data)
        except Exception as exc:
            raise CorpusError(f"{path.name}: schema validation failed: {exc}") from exc
        if path.stem != prompt.id:
            raise CorpusError(
                f"{path.name}: id ({prompt.id!r}) must equal filename stem ({path.stem!r})"
            )
        prompts.append(prompt)
    prompts.sort(key=lambda p: p.id)
    _enforce_cross_rules(prompts)
    return prompts


def _enforce_cross_rules(prompts: list[CorpusPrompt]) -> None:
    from collections import defaultdict
    buckets: dict[tuple[str, str], list[CorpusPrompt]] = defaultdict(list)
    for p in prompts:
        buckets[(p.inspector, p.difficulty)].append(p)
    for (inspector, difficulty), bucket in buckets.items():
        bucket.sort(key=lambda p: p.id)
        nums = [int(p.id.rsplit("__", 1)[-1]) for p in bucket]
        expected = list(range(1, len(nums) + 1))
        if nums != expected:
            raise CorpusError(
                f"{inspector}/{difficulty}: gap in numbering — got {nums}, expected {expected}"
            )
        if difficulty == "super_hard" and len(bucket) >= 5:
            fp_count = sum(1 for p in bucket if p.expected.false_positive)
            if fp_count != 2:
                raise CorpusError(
                    f"{inspector}/super_hard: exactly two false_positive prompts required, got {fp_count}"
                )


def _render_expected_block(p: CorpusPrompt) -> str:
    lines = [
        "",
        "",
        "**Expected SDK behavior:**",
        "",
        f"- action: `{p.expected.action}` at `{p.expected.phase}`",
        f"- findings: `{p.expected.findings}` ({p.expected.tolerance} match)",
    ]
    if p.expected.refusal_code:
        lines.append(f"- refusal_code: `{p.expected.refusal_code}`")
    if p.expected.false_positive:
        lines.append("- ⚠️ `false_positive: true` — this is a precision-test prompt; SDK must NOT block it.")
    if p.requires_extra:
        lines.append(f"- ⚠️ Requires the `[{p.requires_extra}]` extra; without it the SDK will not detect this and the request passes through.")
    if p.references:
        lines.append("- references: " + ", ".join(p.references))
    return "\n".join(lines)


def to_openapi_examples(prompts: list[CorpusPrompt]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for p in prompts:
        out[p.id] = {
            "summary": p.swagger_summary,
            "description": p.swagger_description.rstrip() + _render_expected_block(p),
            "value": p.request,
        }
    return out
