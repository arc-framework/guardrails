"""Unit tests for the observability hook surface."""

from __future__ import annotations

from arc_guard_core.observability import (
    Logger,
    MetricSink,
    NullLogger,
    NullMetricSink,
    NullTracer,
    Tracer,
)


def test_null_tracer_satisfies_protocol() -> None:
    tracer: Tracer = NullTracer()
    with tracer.start_span("op", attributes={"k": "v"}) as span:
        # span returns None from nullcontext
        assert span is None


def test_null_logger_satisfies_protocol_and_bind_returns_logger() -> None:
    logger: Logger = NullLogger()
    bound = logger.bind(request_id="r1")
    assert isinstance(bound, NullLogger)
    bound.event("ok", level="info", x=1)


def test_null_metrics_satisfies_protocol() -> None:
    sink: MetricSink = NullMetricSink()
    sink.counter("n", 3)
    sink.histogram("h", 0.5, attributes={"a": "b"})


def test_runtime_isinstance_checks() -> None:
    assert isinstance(NullTracer(), Tracer)
    assert isinstance(NullLogger(), Logger)
    assert isinstance(NullMetricSink(), MetricSink)
