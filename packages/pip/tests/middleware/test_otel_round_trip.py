"""End-to-end OTEL round-trip via the in-memory span exporter.

Boots an ``InMemorySpanExporter`` on a fresh ``TracerProvider``, wraps
it with ``OtelTracer``, runs span emissions through the adapter, and
asserts the captured spans surface in the in-memory collector with
the documented names + attributes. Pairs with the conformance test:
conformance verifies the *interface* shape, this verifies the *export*
path actually delivers spans to a sink.
"""

from __future__ import annotations

import pytest

otel = pytest.importorskip("opentelemetry")

from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)

from arc_guard.middleware.otel import OtelTracer  # noqa: E402


@pytest.fixture
def in_memory_setup() -> tuple[OtelTracer, InMemorySpanExporter]:
    """Independent TracerProvider so this test does not pollute global state."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    raw_tracer = provider.get_tracer("round-trip-test")
    return OtelTracer(raw_tracer), exporter


def test_single_span_round_trips(in_memory_setup: tuple[OtelTracer, InMemorySpanExporter]) -> None:
    tracer, exporter = in_memory_setup

    with tracer.start_span("guard.stage.classify", attributes={"stage": "classify"}):
        pass

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "guard.stage.classify"
    assert span.attributes is not None
    assert span.attributes.get("stage") == "classify"


def test_nested_spans_round_trip_in_order(
    in_memory_setup: tuple[OtelTracer, InMemorySpanExporter],
) -> None:
    tracer, exporter = in_memory_setup

    with tracer.start_span("guard.stage.classify", attributes={"stage": "classify"}):
        with tracer.start_span("guard.stage.route", attributes={"stage": "route"}):
            pass

    spans = exporter.get_finished_spans()
    assert len(spans) == 2
    inner_span = next(s for s in spans if s.name == "guard.stage.route")
    outer_span = next(s for s in spans if s.name == "guard.stage.classify")
    # Inner span finishes first (LIFO context exit).
    assert inner_span.end_time is not None
    assert outer_span.end_time is not None
    assert inner_span.end_time <= outer_span.end_time


def test_span_attributes_are_preserved(
    in_memory_setup: tuple[OtelTracer, InMemorySpanExporter],
) -> None:
    tracer, exporter = in_memory_setup

    with tracer.start_span(
        "guard.stage.execute",
        attributes={"correlation_id": "c1", "decision_id": "d1", "stage": "execute"},
    ):
        pass

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    attrs = dict(spans[0].attributes or {})
    assert attrs == {"correlation_id": "c1", "decision_id": "d1", "stage": "execute"}
