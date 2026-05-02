"""Pre-validation rejection emits ``guard.request.rejected``.

When ``validate_request_with_observability`` wraps a validator that
raises ``ApiBoundaryValidationError``, the helper must emit the
documented event + counter and re-raise the typed exception so the
caller still sees the rejection.
"""

from __future__ import annotations

import pytest
from arc_guard_core.exceptions import ApiBoundaryValidationError
from arc_guard_core.types import GuardInput

from arc_guard.observability import (
    REQUEST_REJECTED_COUNTER,
    REQUEST_REJECTED_EVENT,
    RecordingLogger,
    RecordingMetricSink,
    emit_request_rejected,
    validate_request_with_observability,
)


def _failing_validator(payload):  # type: ignore[no-untyped-def]
    raise ApiBoundaryValidationError(
        "missing required field: text",
        code="api.missing_field",
        details={"field": "text"},
    )


def _passing_validator(payload):  # type: ignore[no-untyped-def]
    return GuardInput(text=payload["text"])


def test_validation_failure_emits_rejection_event_and_counter() -> None:
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()

    with pytest.raises(ApiBoundaryValidationError):
        validate_request_with_observability(
            _failing_validator,
            {"not_text": "oops"},
            correlation_id="test-corr",
            logger=logger,
            metric_sink=metric_sink,
        )

    rejected = [e for e in logger.captured_events if e.name == REQUEST_REJECTED_EVENT]
    assert len(rejected) == 1
    event = rejected[0]
    assert event.fields["failure_class"] == "api_validation"
    assert event.fields["posture"] == "closed"
    assert event.fields["exception_type"] == "ApiBoundaryValidationError"
    assert event.fields["correlation_id"] == "test-corr"
    assert event.fields["code"] == "api.missing_field"

    counters = [m for m in metric_sink.captured_metrics if m.name == REQUEST_REJECTED_COUNTER]
    assert len(counters) == 1
    assert counters[0].attributes["failure_class"] == "api_validation"


def test_validation_success_passes_through_without_emitting() -> None:
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()

    result = validate_request_with_observability(
        _passing_validator,
        {"text": "hello"},
        correlation_id="test-corr",
        logger=logger,
        metric_sink=metric_sink,
    )

    assert isinstance(result, GuardInput)
    assert result.text == "hello"
    assert logger.captured_events == []
    assert metric_sink.captured_metrics == []


def test_emit_request_rejected_helper_directly() -> None:
    """Operators who do their own validation can call the helper directly."""
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()

    exc = ApiBoundaryValidationError(
        "type mismatch on text",
        code="api.type_mismatch",
        details={"field": "text"},
    )
    emit_request_rejected(
        exc=exc,
        correlation_id="direct-corr",
        logger=logger,
        metric_sink=metric_sink,
    )

    rejected = [e for e in logger.captured_events if e.name == REQUEST_REJECTED_EVENT]
    assert len(rejected) == 1
    assert rejected[0].fields["correlation_id"] == "direct-corr"
