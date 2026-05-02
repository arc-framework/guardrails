"""Transport failures don't escape: adapter swallows + counts.

Constructs an ``OtelMetricSink`` whose underlying meter raises on
``create_counter`` / ``create_histogram`` and asserts that
``counter()`` / ``histogram()`` calls never raise — the sink falls
through to the documented ``arc_guardrails.observability.export_failed``
counter (or, if even that fails, drops silently).

This proves the contract: observability emissions are non-blocking
even when the backend is misconfigured or unreachable.
"""

from __future__ import annotations

from typing import Any

import pytest

otel = pytest.importorskip("opentelemetry")

from arc_guard.middleware.otel import OtelMetricSink  # noqa: E402


class _ExplodingMeter:
    """Meter whose instrument-creation methods always raise."""

    def create_counter(self, name: str, **kwargs: Any) -> Any:
        raise RuntimeError(f"synthetic export failure for counter {name!r}")

    def create_histogram(self, name: str, **kwargs: Any) -> Any:
        raise RuntimeError(f"synthetic export failure for histogram {name!r}")


def test_counter_swallows_create_failure() -> None:
    sink = OtelMetricSink(_ExplodingMeter())  # type: ignore[arg-type]
    # Must not raise. The sink tries to create a counter; the meter
    # explodes; the sink tries to record the export-failure counter;
    # that meter call ALSO explodes; the sink swallows.
    sink.counter("guard.test.counter", attributes={"stage": "test"})


def test_histogram_swallows_create_failure() -> None:
    sink = OtelMetricSink(_ExplodingMeter())  # type: ignore[arg-type]
    sink.histogram("guard.test.histogram", 0.5, attributes={"stage": "test"})


def test_repeated_calls_after_failure_remain_stable() -> None:
    sink = OtelMetricSink(_ExplodingMeter())  # type: ignore[arg-type]
    for _ in range(50):
        sink.counter("guard.repeated", attributes={"stage": "test"})
        sink.histogram("guard.repeated", 1.0, attributes={"stage": "test"})


class _PartiallyExplodingMeter:
    """Counter creation succeeds; histogram creation raises.

    Lets us verify the sink's per-instrument-kind isolation: a broken
    histogram path must not poison the counter path.
    """

    def __init__(self) -> None:
        self.counter_calls: list[tuple[str, int, dict[str, Any] | None]] = []

    def create_counter(self, name: str, **kwargs: Any) -> _RecordingCounter:
        return _RecordingCounter(name, self.counter_calls)

    def create_histogram(self, name: str, **kwargs: Any) -> Any:
        raise RuntimeError("histograms unavailable in this backend")


class _RecordingCounter:
    def __init__(
        self, name: str, sink: list[tuple[str, int, dict[str, Any] | None]],
    ) -> None:
        self._name = name
        self._sink = sink

    def add(self, value: int, *, attributes: dict[str, Any] | None = None) -> None:
        self._sink.append((self._name, value, attributes))


def test_partial_failure_does_not_poison_other_instrument_kind() -> None:
    meter = _PartiallyExplodingMeter()
    sink = OtelMetricSink(meter)  # type: ignore[arg-type]

    # Histogram path explodes; counter path must still work.
    sink.histogram("guard.partial.hist", 1.0, attributes={"stage": "test"})
    sink.counter("guard.partial.counter", attributes={"stage": "test"})

    # The counter add should have landed plus the export-failed
    # counter from the histogram failure.
    counter_names = {call[0] for call in meter.counter_calls}
    assert "guard.partial.counter" in counter_names
    assert "arc_guardrails.observability.export_failed" in counter_names
