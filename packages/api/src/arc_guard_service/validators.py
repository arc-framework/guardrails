"""API-boundary request validators.

Validates incoming request payloads at the API edge before any pipeline
work begins. Failures surface as ``ApiBoundaryValidationError`` with the
offending field listed in ``details``.

This module ships only the request validator; the response validator and
full route plumbing land in the future deployment-surface implementation.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from arc_guard_core.exceptions import ApiBoundaryValidationError
from arc_guard_core.types import GuardContext, GuardInput

ALLOWED_REQUEST_KEYS = {
    "text",
    "context",
    "policy_hints",
}
ALLOWED_CONTEXT_KEYS = {
    "source",
    "user_id",
    "session_id",
    "correlation_id",
    "metadata",
}


def validate_request_payload(payload: Mapping[str, Any]) -> GuardInput:
    """Convert an arbitrary mapping into a typed ``GuardInput`` or raise.

    Validation rules:
    - Unknown top-level keys are rejected.
    - ``text`` is required and must be a string.
    - ``context`` (optional) must be a mapping with only allowed keys.
    - ``policy_hints`` (optional) must be a sequence of strings.
    """
    if not isinstance(payload, Mapping):
        raise ApiBoundaryValidationError(
            "request payload must be a JSON object",
            code="api.malformed_payload",
            details={"got": type(payload).__name__},
        )

    unknown = set(payload.keys()) - ALLOWED_REQUEST_KEYS
    if unknown:
        raise ApiBoundaryValidationError(
            f"unknown request fields: {sorted(unknown)}",
            code="api.unknown_field",
            details={"fields": sorted(unknown)},
        )

    if "text" not in payload:
        raise ApiBoundaryValidationError(
            "missing required field: text",
            code="api.missing_field",
            details={"field": "text"},
        )

    text = payload["text"]
    if not isinstance(text, str):
        raise ApiBoundaryValidationError(
            "text must be a string",
            code="api.type_mismatch",
            details={"field": "text", "got": type(text).__name__},
        )

    context = GuardContext()
    if "context" in payload:
        ctx_in = payload["context"]
        if not isinstance(ctx_in, Mapping):
            raise ApiBoundaryValidationError(
                "context must be a JSON object",
                code="api.type_mismatch",
                details={"field": "context", "got": type(ctx_in).__name__},
            )
        unknown_ctx = set(ctx_in.keys()) - ALLOWED_CONTEXT_KEYS
        if unknown_ctx:
            raise ApiBoundaryValidationError(
                f"unknown context fields: {sorted(unknown_ctx)}",
                code="api.unknown_field",
                details={"fields": sorted(unknown_ctx), "where": "context"},
            )
        source = ctx_in.get("source", "input")
        if source not in {"input", "output"}:
            raise ApiBoundaryValidationError(
                "context.source must be 'input' or 'output'",
                code="api.type_mismatch",
                details={"field": "context.source", "got": repr(source)},
            )
        context = GuardContext(
            source=source,
            user_id=ctx_in.get("user_id"),
            session_id=ctx_in.get("session_id"),
            correlation_id=ctx_in.get("correlation_id"),
            metadata=dict(ctx_in.get("metadata", {})),
        )

    hints: frozenset[str] = frozenset()
    if "policy_hints" in payload:
        raw = payload["policy_hints"]
        if not isinstance(raw, (list, tuple, set, frozenset)):
            raise ApiBoundaryValidationError(
                "policy_hints must be an array of strings",
                code="api.type_mismatch",
                details={"field": "policy_hints", "got": type(raw).__name__},
            )
        try:
            hints = frozenset(str(h) for h in raw)
        except Exception as exc:
            raise ApiBoundaryValidationError(
                "policy_hints contains a non-string entry",
                code="api.type_mismatch",
                details={"field": "policy_hints"},
                cause=exc,
            ) from exc

    return GuardInput(text=text, context=context, policy_hints=hints)


__all__ = ["validate_request_payload"]
