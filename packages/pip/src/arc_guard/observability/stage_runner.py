"""Stage instrumentation context-manager.

Wraps each pipeline stage with a span + ``guard.stage.started`` /
``guard.stage.completed`` events + a ``arc_guardrails.stage.duration``
histogram sample. Stage validity is enforced against
``STAGE_DESCRIPTORS`` so typos cannot leak into the metric label space.

US1 (initial wiring) shipped the minimal happy-path instrumentation. US2
adds the ``BoundedRedactor`` integration: every span attribute, log
field, and metric label is sanitized before emission; rejected
attributes are dropped and counted via
``arc_guardrails.observability.attribute_dropped``. The full
``FAIL_RULE`` posture-aware branching lands in US3 (T037); sampling and
log-level-floor land in US6.
"""

from __future__ import annotations

import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from arc_guard_core.observability import Logger, MetricSink, Tracer
from arc_guard_core.protocols.attribute_redactor import AttributeRedactor
from arc_guard_core.stages import STAGE_DESCRIPTORS

ATTRIBUTE_DROPPED_COUNTER = "arc_guardrails.observability.attribute_dropped"
ATTRIBUTE_DROPPED_EVENT = "guard.observability.attribute_dropped"


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
    untouched (the US1-MVP behavior).

    Failure mode: re-raises any exception unchanged. The full
    failure-mode contract (posture-aware branching, refusal envelope
    construction, severity-mapped log level) lands in US3.
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
    with tracer.start_span(f"guard.stage.{stage}", attributes=span_attrs):
        logger.event("guard.stage.started", level="info", **span_attrs)
        try:
            yield None
        finally:
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


__all__ = ["stage_runner"]
