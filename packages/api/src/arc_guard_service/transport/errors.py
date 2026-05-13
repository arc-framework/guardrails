"""Translate ``PipelineError`` instances to HTTP responses.

The mapping consults the ``FAIL_RULE`` table from ``arc_guard_core.failure_modes``
and returns ``(http_status, RefusalEnvelope)``. The envelope is built from the
registered default ``RefusalTemplate`` for the rule's refusal code; raw
exception messages and stack traces never reach the response body.
"""

from __future__ import annotations

from arc_guard_core.exceptions import ArcGuardError
from arc_guard_core.failure_modes import lookup_rule
from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.refusal.templates import get_refusal_template
from arc_guard_core.types import RefusalEnvelope

_REFUSAL_CODE_TO_STATUS: dict[RefusalCode, int] = {
    RefusalCode.API_INVALID_REQUEST: 400,
    RefusalCode.API_TRANSPORT_TIMEOUT: 504,
}


def _resolve_status(rule_severity: str, refusal_code: RefusalCode | None) -> int:
    """Return the HTTP status for a (severity, refusal_code) pair.

    Recognized transport-layer refusal codes (``API_INVALID_REQUEST``,
    ``API_TRANSPORT_TIMEOUT``) map to specific 4xx/504 statuses regardless
    of severity — the refusal code is the explicit signal. Severity only
    drives the fallback mapping for codes that lack a specific HTTP slot.
    """
    if refusal_code is not None and refusal_code in _REFUSAL_CODE_TO_STATUS:
        return _REFUSAL_CODE_TO_STATUS[refusal_code]
    if rule_severity == "warn":
        return 422
    return 500


def _envelope_for_code(
    code: RefusalCode,
    *,
    trigger: str,
    policy: str,
) -> RefusalEnvelope:
    template = get_refusal_template(code)
    return RefusalEnvelope(
        code=code.value,
        trigger=trigger,
        policy=policy,
        human_message=template.human_message,
        next_steps=template.next_steps,
    )


def pipeline_error_to_http(exc: ArcGuardError) -> tuple[int, RefusalEnvelope]:
    """Map an ``ArcGuardError`` to ``(http_status, refusal_envelope)``.

    Reads the FAIL_RULE table for ``type(exc)``. ``severity="warn"`` →
    HTTP 422; ``severity="error"`` with a recognized transport-layer
    refusal code → 4xx/504; otherwise → 500. The envelope's
    ``human_message`` and ``next_steps`` come from the registered template
    for the refusal code, never from ``str(exc)``.

    Accepts the broad ``ArcGuardError`` base so transport-layer callers
    can pass either ``PipelineError`` subclasses or boundary-validation
    failures like ``ApiBoundaryValidationError``.
    """
    rule, _posture = lookup_rule(type(exc))
    code = rule.refusal_code or RefusalCode.INTERNAL_PIPELINE_ERROR
    status = _resolve_status(rule.severity, rule.refusal_code)
    envelope = _envelope_for_code(
        code,
        trigger=exc.code,
        policy=rule.failure_class,
    )
    return status, envelope


def envelope_for_invalid_request(
    *,
    trigger: str,
    policy: str = "api_validation",
) -> RefusalEnvelope:
    """Build a 400-equivalent envelope for malformed-request paths."""
    return _envelope_for_code(
        RefusalCode.API_INVALID_REQUEST,
        trigger=trigger,
        policy=policy,
    )


def envelope_for_transport_timeout(
    *,
    trigger: str = "transport.timeout",
    policy: str = "api_transport",
) -> RefusalEnvelope:
    """Build a 504-equivalent envelope for transport-timeout paths."""
    return _envelope_for_code(
        RefusalCode.API_TRANSPORT_TIMEOUT,
        trigger=trigger,
        policy=policy,
    )


__all__ = [
    "pipeline_error_to_http",
    "envelope_for_invalid_request",
    "envelope_for_transport_timeout",
]
