"""Wrapper that emits a ``guard.request.rejected`` event on validation failure.

API-boundary validation runs *before* the pipeline. When it rejects a
request, no pipeline stage executes, so the in-pipeline observability
never fires. This helper wraps a validation callable and emits a
single ``guard.request.rejected`` event + counter when validation
raises ``ApiBoundaryValidationError`` (or any other validation
error). The exception is re-raised after the emission so callers
still see the typed failure.

Use it from API-handling code that owns the ``Tracer`` / ``Logger``
/ ``MetricSink`` references; the helper does not modify the validator
itself.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, TypeVar

from arc_guard_core.exceptions import ApiBoundaryValidationError, ArcGuardError
from arc_guard_core.failure_modes import lookup_rule
from arc_guard_core.observability import Logger, MetricSink

REQUEST_REJECTED_EVENT = "guard.request.rejected"
REQUEST_REJECTED_COUNTER = "arc_guardrails.request.rejected"

T = TypeVar("T")


def emit_request_rejected(
    *,
    exc: BaseException,
    correlation_id: str,
    logger: Logger,
    metric_sink: MetricSink,
) -> None:
    """Emit the documented rejection event + counter.

    Used internally by ``validate_request_with_observability`` and
    available to callers who do their own validation but want the
    same emission shape.
    """
    rule, posture = lookup_rule(type(exc))
    fields: dict[str, Any] = {
        "correlation_id": correlation_id,
        "failure_class": rule.failure_class,
        "posture": posture,
        "exception_type": type(exc).__name__,
    }
    code = getattr(exc, "code", None)
    if code:
        fields["code"] = str(code)
    logger.event(REQUEST_REJECTED_EVENT, level=rule.severity, **fields)
    metric_sink.counter(
        REQUEST_REJECTED_COUNTER,
        attributes={"failure_class": rule.failure_class, "posture": posture},
    )


def validate_request_with_observability(
    validator: Callable[[Mapping[str, Any]], T],
    payload: Mapping[str, Any],
    *,
    correlation_id: str,
    logger: Logger,
    metric_sink: MetricSink,
) -> T:
    """Run ``validator(payload)`` with rejection observability.

    On success: returns the validator's result (typically a typed
    ``GuardInput``).
    On ``ApiBoundaryValidationError`` (or any ``ArcGuardError``):
    emits ``guard.request.rejected`` + the counter, then re-raises.
    Other exceptions pass through unchanged so the caller can decide
    how to handle uncategorized failures.
    """
    try:
        return validator(payload)
    except ArcGuardError as exc:
        emit_request_rejected(
            exc=exc,
            correlation_id=correlation_id,
            logger=logger,
            metric_sink=metric_sink,
        )
        raise


__all__ = [
    "REQUEST_REJECTED_EVENT",
    "REQUEST_REJECTED_COUNTER",
    "emit_request_rejected",
    "validate_request_with_observability",
    "ApiBoundaryValidationError",
]
