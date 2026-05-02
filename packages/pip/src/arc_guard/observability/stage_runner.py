"""Stage instrumentation context-manager.

Wraps each pipeline stage with a span + ``guard.stage.started`` /
``guard.stage.completed`` events + a ``arc_guardrails.stage.duration``
histogram sample. Stage validity is enforced against
``STAGE_DESCRIPTORS`` so typos cannot leak into the metric label space.

When a ``BoundedRedactor`` is supplied, every span attribute, log
field, and metric label is sanitized before emission; rejected
attributes are dropped and counted via
``arc_guardrails.observability.attribute_dropped``. On exception, the
``FAIL_RULE`` for the exception's MRO is looked up and a
``guard.stage.failed`` event + counter fire at the rule's severity;
the exception is re-raised so the caller can apply posture-specific
behavior.
"""

from __future__ import annotations

import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from arc_guard_core.failure_modes import lookup_rule
from arc_guard_core.observability import Logger, MetricSink, Tracer
from arc_guard_core.protocols.attribute_redactor import AttributeRedactor
from arc_guard_core.stages import STAGE_DESCRIPTORS

ATTRIBUTE_DROPPED_COUNTER = "arc_guardrails.observability.attribute_dropped"
ATTRIBUTE_DROPPED_EVENT = "guard.observability.attribute_dropped"
STAGE_FAILED_EVENT = "guard.stage.failed"
STAGE_FAILED_COUNTER = "arc_guardrails.stage.failed"


def emit_stage_failed(
    *,
    stage: str,
    exc: BaseException,
    correlation_id: str,
    decision_id: str,
    logger: Logger,
    metric_sink: MetricSink,
    duration_ms: float | None = None,
) -> None:
    """Emit the documented ``guard.stage.failed`` event + counter.

    Used by both ``stage_runner``'s catch-block (for failures that
    escape the yielded body) and by per-stage call sites that have
    their own try/except discipline (notably the inspector loop's
    fail-open per-inspector handling). Calling either path produces
    the same observability emission so failure-mode coverage holds
    regardless of where the exception was caught.
    """
    rule, posture = lookup_rule(type(exc))
    failure_attrs: dict[str, Any] = {
        "correlation_id": correlation_id,
        "decision_id": decision_id,
        "stage": stage,
        "failure_class": rule.failure_class,
        "posture": posture,
        "exception_type": type(exc).__name__,
    }
    if duration_ms is not None:
        failure_attrs["duration_ms"] = duration_ms
    logger.event(STAGE_FAILED_EVENT, level=rule.severity, **failure_attrs)
    metric_sink.counter(
        STAGE_FAILED_COUNTER,
        attributes={
            "stage": stage,
            "failure_class": rule.failure_class,
            "posture": posture,
        },
    )


def _redact_attributes(
    attributes: Mapping[str, Any],
    *,
    redactor: AttributeRedactor | None,
    metric_sink: MetricSink | None,
    logger: Logger | None,
    is_metric: bool,
    stage: str,
) -> dict[str, Any]:
    """Apply the redactor to every (key, value) pair; drop rejected ones.

    Each dropped attribute increments the
    ``arc_guardrails.observability.attribute_dropped`` counter with a
    ``reason`` label, and emits a ``guard.observability.attribute_dropped``
    structured event so the drop is visible to operators.
    """
    if redactor is None:
        return dict(attributes)

    accepted: dict[str, Any] = {}
    for key, value in attributes.items():
        # Metric path uses ``sanitize_metric_label`` which enforces the
        # allow-list in addition to byte cap + substring search.
        if is_metric and hasattr(redactor, "sanitize_metric_label"):
            result = redactor.sanitize_metric_label(key, value)
        else:
            result = redactor.sanitize(key, value)
        if result.accepted:
            accepted[key] = result.value if result.value is not None else value
            continue
        # Reject — count and log the drop.
        if metric_sink is not None:
            metric_sink.counter(
                ATTRIBUTE_DROPPED_COUNTER,
                attributes={"stage": stage, "reason": result.reason or "unknown"},
            )
        if logger is not None:
            logger.event(
                ATTRIBUTE_DROPPED_EVENT,
                level="warn",
                stage=stage,
                attribute_key=key,
                reason=result.reason or "unknown",
            )
    return accepted


@contextmanager
def stage_runner(
    stage: str,
    *,
    correlation_id: str,
    decision_id: str,
    tracer: Tracer,
    logger: Logger,
    metric_sink: MetricSink,
    redactor: AttributeRedactor | None = None,
) -> Iterator[None]:
    """Wrap a pipeline stage with span / event / metric emissions.

    When ``redactor`` is provided, every attribute / field / label is
    sanitized via the redactor before reaching the backend. Rejected
    attributes are dropped and counted; the stage continues without
    them. When ``redactor`` is ``None``, attributes pass through
    untouched.

    Failure mode: emits ``guard.stage.failed`` and re-raises. The
    posture-driven refusal-envelope construction and short-circuit
    live in the pipeline so existing fail-open behavior for inspector
    and reporter failures stays intact.
    """
    if stage not in STAGE_DESCRIPTORS:
        raise ValueError(
            f"unknown pipeline stage {stage!r}; expected one of {sorted(STAGE_DESCRIPTORS)}"
        )

    common_raw: dict[str, Any] = {
        "correlation_id": correlation_id,
        "decision_id": decision_id,
        "stage": stage,
    }
    # Span and log paths share the same allow-listed common envelope.
    span_attrs = _redact_attributes(
        common_raw,
        redactor=redactor,
        metric_sink=metric_sink,
        logger=logger,
        is_metric=False,
        stage=stage,
    )
    metric_attrs = _redact_attributes(
        common_raw,
        redactor=redactor,
        metric_sink=metric_sink,
        logger=logger,
        is_metric=True,
        stage=stage,
    )

    started_ns = time.monotonic_ns()
    raised: BaseException | None = None
    with tracer.start_span(f"guard.stage.{stage}", attributes=span_attrs):
        logger.event("guard.stage.started", level="info", **span_attrs)
        try:
            yield None
        except BaseException as exc:
            raised = exc
            ended_ns = time.monotonic_ns()
            duration_ms = (ended_ns - started_ns) / 1_000_000
            # Posture is read from the foundation ``__failure_mode__``
            # ClassVar (the single source of truth) so stage_runner
            # cannot drift from the foundation contract.
            emit_stage_failed(
                stage=stage,
                exc=exc,
                correlation_id=correlation_id,
                decision_id=decision_id,
                logger=logger,
                metric_sink=metric_sink,
                duration_ms=duration_ms,
            )
            # Re-raise so the pipeline's existing try/except logic can
            # apply the posture-specific behavior. Posture-driven
            # short-circuit and conservative-default substitution live
            # in the pipeline, not here, so existing fail-open behavior
            # for InspectorError / ReporterError remains intact.
            raise
        finally:
            if raised is None:
                ended_ns = time.monotonic_ns()
                duration_ms = (ended_ns - started_ns) / 1_000_000
                logger.event(
                    "guard.stage.completed",
                    level="info",
                    duration_ms=duration_ms,
                    status="ok",
                    **span_attrs,
                )
                metric_sink.histogram(
                    "arc_guardrails.stage.duration",
                    duration_ms,
                    attributes=metric_attrs,
                )


__all__ = ["stage_runner", "emit_stage_failed"]
