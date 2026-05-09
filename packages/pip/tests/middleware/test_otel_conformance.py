"""``OtelObservability`` adapters satisfy the foundation Protocols.

Each adapter must structurally match its corresponding
``runtime_checkable`` Protocol from ``arc_guard_core.observability``
so the pipeline can use it as a drop-in replacement for the null
default. The Protocols enforce method names, parameter shapes, and
the contract docstring's "implementations must not raise" rule —
verified here by exercising each method and asserting no exception
escapes.
"""

from __future__ import annotations

import pytest

otel = pytest.importorskip("opentelemetry")

from arc_guard_core.observability import Logger, MetricSink, Tracer  # noqa: E402

from arc_guard.middleware.otel import (  # noqa: E402
    OtelLogger,
    OtelMetricSink,
    OtelObservability,
    OtelTracer,
)


@pytest.fixture
def adapters() -> OtelObservability:
    return OtelObservability.from_otel_sdk(instrumentation_name="conformance-test")


def test_tracer_satisfies_protocol(adapters: OtelObservability) -> None:
    assert isinstance(adapters.tracer, OtelTracer)
    assert isinstance(adapters.tracer, Tracer)


def test_logger_satisfies_protocol(adapters: OtelObservability) -> None:
    assert isinstance(adapters.logger, OtelLogger)
    assert isinstance(adapters.logger, Logger)


def test_metric_sink_satisfies_protocol(adapters: OtelObservability) -> None:
    assert isinstance(adapters.metric_sink, OtelMetricSink)
    assert isinstance(adapters.metric_sink, MetricSink)


def test_tracer_start_span_returns_context_manager(adapters: OtelObservability) -> None:
    cm = adapters.tracer.start_span("conformance.span", attributes={"k": "v"})
    with cm:
        pass  # entering and exiting must not raise


def test_logger_bind_returns_logger(adapters: OtelObservability) -> None:
    bound = adapters.logger.bind(extra="field")
    assert isinstance(bound, OtelLogger)
    assert isinstance(bound, Logger)
    bound.event("conformance.event", level="info", payload="ok")


def test_logger_event_accepts_all_documented_levels(adapters: OtelObservability) -> None:
    for level in ("debug", "info", "warn", "error", "critical"):
        adapters.logger.event(f"conformance.{level}", level=level)


def test_metric_sink_counter_and_histogram(adapters: OtelObservability) -> None:
    adapters.metric_sink.counter("conformance.counter", attributes={"stage": "test"})
    adapters.metric_sink.histogram(
        "conformance.histogram", 1.23, attributes={"stage": "test"},
    )


def test_metric_sink_caches_instruments(adapters: OtelObservability) -> None:
    """Same name on repeat counter() calls must reuse the OTEL instrument."""
    adapters.metric_sink.counter("conformance.cache", attributes={"stage": "test"})
    adapters.metric_sink.counter("conformance.cache", attributes={"stage": "test"})

    sink = adapters.metric_sink
    assert "conformance.cache" in sink._counters
    assert len(sink._counters) >= 1


def test_no_exception_escapes_on_repeat_calls(adapters: OtelObservability) -> None:
    """Failure-mode rule: implementations must not raise."""
    for _ in range(20):
        with adapters.tracer.start_span("loop"):
            adapters.logger.event("loop", level="info")
            adapters.metric_sink.counter("loop", attributes={"stage": "loop"})
            adapters.metric_sink.histogram("loop", 0.5, attributes={"stage": "loop"})
