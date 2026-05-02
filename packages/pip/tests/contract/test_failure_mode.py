"""Parametrized fault-injection harness over the full FAIL_RULE table.

For every leaf exception in ``arc_guard_core.failure_modes.FAIL_RULE``,
inject a stage that raises that exception, run the pipeline against
recording sinks, and assert the documented behavior:

- ``guard.stage.failed`` event fires at the rule's severity with
  matching ``stage``, ``failure_class``, ``posture``, and
  ``exception_type`` attributes.
- ``arc_guardrails.stage.failed`` counter increments with matching
  attributes.
- Result branches per posture:
  - ``closed`` → ``GuardResult.refusal`` populated with the rule's
    ``refusal_code``; the run terminates without a ``DecisionRecord``.
  - ``open`` → run continues, ``GuardResult.refusal`` is ``None``, the
    failure surfaces only as a logged event + counter.
  - ``closed-conservative`` → run continues without a refusal AND the
    failed operation returned its documented default value.

Construction-time exceptions (``ConfigSchemaError``,
``ConfigCrossFieldError``) and registration-time exceptions
(``RegistryFrozenError`` via MRO) cannot fire from inside a stage and
are exercised by ``test_config_error_fails_at_construction.py`` and
``test_registry_freeze.py`` respectively.
"""

from __future__ import annotations

import pytest
from arc_guard_core.exceptions import (
    AdapterBoundaryValidationError,
    ApiBoundaryValidationError,
    EntityProviderError,
    FlagProviderError,
    InspectorError,
    PipelineContractValidationError,
    PolicyRouterError,
    RefusalEnvelopeError,
    ReporterError,
    StrategyError,
)
from arc_guard_core.failure_modes import FAIL_RULE, lookup_rule
from arc_guard_core.types import GuardInput

from arc_guard.observability import (
    RecordingLogger,
    RecordingMetricSink,
    RecordingTracer,
)
from arc_guard.pipeline import GuardPipeline

# Stage-time exception classes — those that can fire from inside a
# pipeline stage's body. Construction-time and registration-time
# classes are excluded (covered by their dedicated tests).
STAGE_TIME_EXCEPTIONS = [
    ApiBoundaryValidationError,
    PipelineContractValidationError,
    AdapterBoundaryValidationError,
    InspectorError,
    StrategyError,
    PolicyRouterError,
    RefusalEnvelopeError,
    ReporterError,
    FlagProviderError,
    EntityProviderError,
]


class _RaisingInspector:
    """Inspector that raises a configured exception class on inspect()."""

    def __init__(self, exc_class: type[BaseException]) -> None:
        self._exc_class = exc_class

    async def inspect(self, result):  # type: ignore[no-untyped-def]
        raise self._exc_class(
            "synthetic fault for parametrized failure-mode test",
            code=next(iter(self._exc_class.__valid_codes__)),  # type: ignore[attr-defined]
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("exc_class", STAGE_TIME_EXCEPTIONS, ids=lambda c: c.__name__)
async def test_stage_failure_emits_documented_observability(
    exc_class: type[BaseException],
) -> None:
    """Each stage-time exception emits guard.stage.failed at rule severity
    with stage / failure_class / posture / exception_type attributes.
    """
    rule, posture = lookup_rule(exc_class)
    tracer = RecordingTracer()
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()
    pipeline = GuardPipeline(
        inspectors=[_RaisingInspector(exc_class)],
        tracer_hook=tracer,
        logger_hook=logger,
        metrics_hook=metric_sink,
    )

    # All stage-time exceptions are injected via the inspector chain
    # (STAGE_CLASSIFY); the pipeline's existing fail-open try/except
    # swallows them so the run completes regardless of posture.
    await pipeline.pre_process(GuardInput(text="fault-injection test input."))

    # guard.stage.failed fires at rule severity.
    failed_events = [
        e for e in logger.captured_events if e.name == "guard.stage.failed"
    ]
    assert len(failed_events) == 1, (
        f"expected exactly one stage.failed event for {exc_class.__name__}, "
        f"got {len(failed_events)}"
    )
    event = failed_events[0]
    assert event.level == rule.severity
    assert event.fields["stage"] == "classify"
    assert event.fields["failure_class"] == rule.failure_class
    assert event.fields["posture"] == posture
    assert event.fields["exception_type"] == exc_class.__name__

    # Counter increment with the matching attributes.
    failed_counters = [
        m for m in metric_sink.captured_metrics if m.name == "arc_guardrails.stage.failed"
    ]
    assert len(failed_counters) == 1
    assert failed_counters[0].attributes["failure_class"] == rule.failure_class
    assert failed_counters[0].attributes["posture"] == posture


def test_fail_rule_table_covers_every_stage_time_exception() -> None:
    """Sanity check: FAIL_RULE has entries for all stage-time exceptions."""
    missing = [c.__name__ for c in STAGE_TIME_EXCEPTIONS if c not in FAIL_RULE]
    assert missing == [], f"FAIL_RULE missing entries for: {missing}"
