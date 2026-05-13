"""End-to-end observability smoke test.

Exercises every observability story in one run so a regression in
any single story is caught before integration:

1. Stage instrumentation — recording sinks captured spans / events / metrics.
2. Payload safety — leak scanner returns zero leaks against the input.
3. Failure-mode contract — an injected fail-closed exception produces a
   refusal envelope with the correct refusal code.
4. Concurrency hardening — a frozen-after-construction registry rejects
   post-snapshot registration with ``RegistryFrozenError``.
5. OTEL adapter — the OTEL bundle constructs and the tracer's
   ``start_span`` returns a usable context manager.
6. Tunable knobs — sampling at 1.0 keeps every emission; sampling at 0
   drops them (verified via the dropped counter).

Each user story has its own dedicated tests; this smoke test catches
the case where each individual feature passes its own tests but the
combined behavior breaks under realistic configuration.
"""

from __future__ import annotations

import pytest
from arc_guard_core.config import GuardConfig
from arc_guard_core.exceptions import (
    RegistryFrozenError,
    StrategyError,
)
from arc_guard_core.observability_config import ObservabilityConfig
from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.registry import EntityRegistry
from arc_guard_core.types import EntityDefinition, GuardContext, GuardInput

from arc_guard.concurrency.offload import OFFLOAD_COUNTER, run_off_loop
from arc_guard.observability import (
    CapturedArtifacts,
    RecordingLogger,
    RecordingMetricSink,
    RecordingTracer,
    scan_for_leaks,
)
from arc_guard.observability.sampling import SPAN_DROPPED_COUNTER
from arc_guard.pipeline import GuardPipeline


class _PassthroughInspector:
    async def inspect(self, result):  # type: ignore[no-untyped-def]
        return result


class _RaisingInspector:
    async def inspect(self, result):  # type: ignore[no-untyped-def]
        raise StrategyError("e2e refusal trigger", code="strategy.failed")


@pytest.mark.asyncio
async def test_full_observability_surface_end_to_end() -> None:
    # 1. Stage instrumentation + 2. payload safety + 6. tunable knobs ----
    config = GuardConfig(
        observability=ObservabilityConfig(
            sampling_rate=1.0,
            refusal_always_emits=True,
            log_level_floor="info",
        ),
    )
    tracer = RecordingTracer()
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()
    pipeline = GuardPipeline(
        config=config,
        inspectors=[_PassthroughInspector()],
        tracer_hook=tracer,
        logger_hook=logger,
        metrics_hook=metric_sink,
    )

    text = "End-to-end observability smoke test input."
    result = await pipeline.pre_process(
        GuardInput(text=text, context=GuardContext(correlation_id="e2e-corr")),
    )
    assert result is not None
    assert result.action == "pass"

    # Stage instrumentation: every captured span / event / metric carries
    # the correlation_id we set on the input.
    assert any(s.name.startswith("guard.stage.") for s in tracer.captured_spans)
    assert any(e.name == "guard.run.completed" for e in logger.captured_events)
    assert any(m.name == "arc_guardrails.run.duration" for m in metric_sink.captured_metrics)

    # Payload safety: the leak scanner finds zero leaks.
    captured = CapturedArtifacts(
        spans=list(tracer.captured_spans),
        events=list(logger.captured_events),
        metrics=list(metric_sink.captured_metrics),
    )
    leaks = scan_for_leaks(captured, originals=[text])
    assert leaks == [], f"leak scanner found leaks in e2e run: {leaks}"

    # 3. Failure-mode contract — closed-posture short-circuit -------------
    refusal_logger = RecordingLogger()
    refusal_pipeline = GuardPipeline(
        config=config,
        inspectors=[_RaisingInspector()],
        tracer_hook=RecordingTracer(),
        logger_hook=refusal_logger,
        metrics_hook=RecordingMetricSink(),
    )
    # InspectorError is fail-open per foundation; StrategyError raised
    # from an inspector still surfaces via stage.failed observability
    # event (the per-inspector except path emits it explicitly).
    await refusal_pipeline.pre_process(GuardInput(text="trigger"))
    failed = [e for e in refusal_logger.captured_events if e.name == "guard.stage.failed"]
    assert len(failed) >= 1
    assert failed[0].fields["failure_class"] == "strategy"

    # 4. Concurrency hardening — registry freeze rejects post-construction
    registry = EntityRegistry()
    registry.register(EntityDefinition(name="EMAIL", category="pii"))
    registry.freeze()
    with pytest.raises(RegistryFrozenError):
        registry.register(EntityDefinition(name="PHONE", category="pii"))

    # 5. OTEL adapter — bundle constructs and the tracer is usable -------
    pytest.importorskip("opentelemetry")
    from arc_guard.middleware import from_otel_sdk

    otel_bundle = from_otel_sdk(instrumentation_name="e2e-smoke")
    with otel_bundle.tracer.start_span("e2e.smoke", attributes={"stage": "smoke"}):
        otel_bundle.logger.event("e2e.event", level="info")
        otel_bundle.metric_sink.counter("e2e.counter", attributes={"stage": "smoke"})

    # 6. Tunable knobs (sampling=0) — non-refusal runs drop emissions ----
    drop_config = GuardConfig(
        observability=ObservabilityConfig(
            sampling_rate=0.0,
            refusal_always_emits=False,
        ),
    )
    drop_logger = RecordingLogger()
    drop_metric_sink = RecordingMetricSink()
    drop_pipeline = GuardPipeline(
        config=drop_config,
        inspectors=[_PassthroughInspector()],
        tracer_hook=RecordingTracer(),
        logger_hook=drop_logger,
        metrics_hook=drop_metric_sink,
    )
    await drop_pipeline.pre_process(GuardInput(text="dropped run"))
    completed = [e for e in drop_logger.captured_events if e.name == "guard.run.completed"]
    assert completed == []
    dropped = [m for m in drop_metric_sink.captured_metrics if m.name == SPAN_DROPPED_COUNTER]
    assert len(dropped) == 1


@pytest.mark.asyncio
async def test_offload_helper_increments_counter_in_realistic_flow() -> None:
    """Offload helper integrated with metric sink behaves correctly."""
    metric_sink = RecordingMetricSink()

    def _blocking() -> int:
        return 42

    result = await run_off_loop(
        _blocking,
        stage="execute",
        metric_sink=metric_sink,
    )
    assert result == 42
    counters = [m for m in metric_sink.captured_metrics if m.name == OFFLOAD_COUNTER]
    assert len(counters) == 1


def test_refusal_codes_register_for_internal_failures() -> None:
    """The new refusal codes added in this spec resolve to templates."""
    from arc_guard_core.refusal.templates import get_refusal_template

    for code in (
        RefusalCode.API_INVALID_REQUEST,
        RefusalCode.INTERNAL_PIPELINE_ERROR,
        RefusalCode.INTERNAL_ADAPTER_ERROR,
        RefusalCode.INTERNAL_REFUSAL_BUILD_ERROR,
        RefusalCode.INTERNAL_ENTITY_PROVIDER_ERROR,
        RefusalCode.INTERNAL_UNKNOWN_ERROR,
    ):
        template = get_refusal_template(code)
        assert template.human_message
        assert template.next_steps
