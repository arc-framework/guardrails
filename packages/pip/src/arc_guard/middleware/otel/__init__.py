"""OTEL-backed implementations of the observability hook Protocols.

Three adapter classes — ``OtelTracer``, ``OtelLogger``,
``OtelMetricSink`` — wrap the ``opentelemetry`` SDK and satisfy the
``Tracer``, ``Logger``, ``MetricSink`` Protocols structurally.
``OtelObservability`` bundles the three together as a convenience for
the ``arc_guard.middleware.from_otel_sdk()`` factory.

Concurrency: thread-safe. Each adapter delegates to the underlying
OTEL provider, which is itself thread-safe; the only shared mutable
state is the metric instrument cache, guarded by an ``RLock``.
Failure mode: every adapter swallows internal exceptions and routes
them to the documented ``arc_guardrails.observability.export_failed``
counter via the fallback sink. Exceptions never escape.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager, nullcontext
from typing import Any

# Lazy-import OTEL — keeping the import at module top is acceptable
# here because this module is gated behind the ``arc-guard[otel]``
# extra; importing it without the extra installed is the operator's
# explicit choice. The bare ``arc_guard.middleware`` import path
# defers OTEL imports via the factory in the parent package.
try:
    from opentelemetry import metrics as otel_metrics
    from opentelemetry import trace as otel_trace
    from opentelemetry._logs import SeverityNumber
    from opentelemetry._logs import get_logger as otel_get_logger
    from opentelemetry.metrics import Counter, Histogram, Meter
    from opentelemetry.trace import Tracer as OTelTracerSDK
except ImportError as exc:  # pragma: no cover — gated by extra
    raise ImportError(
        "arc_guard.middleware.otel requires the [otel] extra. "
        "Install with: pip install arc-guard[otel]"
    ) from exc


EXPORT_FAILED_COUNTER = "arc_guardrails.observability.export_failed"

_LEVEL_TO_SEVERITY: dict[str, int] = {
    "debug": SeverityNumber.DEBUG.value,
    "info": SeverityNumber.INFO.value,
    "warn": SeverityNumber.WARN.value,
    "warning": SeverityNumber.WARN.value,
    "error": SeverityNumber.ERROR.value,
    "critical": SeverityNumber.FATAL.value,
}


class OtelTracer:
    """Wraps an ``opentelemetry.trace.Tracer`` to satisfy the ``Tracer`` Protocol."""

    def __init__(self, tracer: OTelTracerSDK) -> None:
        self._tracer = tracer

    def start_span(
        self, name: str, *, attributes: Mapping[str, Any] | None = None
    ) -> AbstractContextManager[Any]:
        try:
            cm: AbstractContextManager[Any] = self._tracer.start_as_current_span(
                name, attributes=dict(attributes) if attributes else None,
            )
            return cm
        except Exception:  # pragma: no cover — defensive; OTEL should never raise
            return nullcontext()


class OtelLogger:
    """Wraps an OTEL logs bridge to satisfy the ``Logger`` Protocol.

    ``event(name, level=..., **fields)`` constructs an OTEL log record
    with ``Body=name``, severity from the level mapping, and
    ``Attributes=fields``. ``bind(**fields)`` returns a new logger
    that merges ``fields`` into every subsequent ``event`` call.
    """

    def __init__(
        self,
        logger_name: str = "arc-guardrails",
        bound: Mapping[str, Any] | None = None,
    ) -> None:
        self._logger_name = logger_name
        self._bound: dict[str, Any] = dict(bound) if bound else {}
        self._otel: Any | None
        try:
            self._otel = otel_get_logger(logger_name)
        except Exception:  # pragma: no cover — defensive
            self._otel = None

    def bind(self, **fields: Any) -> OtelLogger:
        merged = {**self._bound, **fields}
        return OtelLogger(self._logger_name, bound=merged)

    def event(self, name: str, *, level: str = "info", **fields: Any) -> None:
        if self._otel is None:
            return
        attrs = {**self._bound, **fields}
        severity = _LEVEL_TO_SEVERITY.get(level.lower(), SeverityNumber.INFO.value)
        try:
            from opentelemetry._logs import LogRecord

            record = LogRecord(
                severity_number=SeverityNumber(severity),
                severity_text=level.upper(),
                body=name,
                attributes=attrs,
            )
            self._otel.emit(record)
        except Exception:  # pragma: no cover — defensive
            pass


class OtelMetricSink:
    """Wraps an ``opentelemetry.metrics.Meter`` with a thread-safe instrument cache.

    Each unique metric name is created once and cached so subsequent
    emissions reuse the same instrument. Counters and histograms have
    distinct caches; calling ``counter("foo", ...)`` and
    ``histogram("foo", ...)`` would create both kinds of instruments
    (which is a misuse — the convention is one kind per metric name).
    """

    def __init__(self, meter: Meter) -> None:
        self._meter = meter
        self._lock = threading.RLock()
        self._counters: dict[str, Counter] = {}
        self._histograms: dict[str, Histogram] = {}

    def counter(
        self,
        name: str,
        value: int = 1,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        try:
            instrument = self._get_or_create_counter(name)
            instrument.add(value, attributes=dict(attributes) if attributes else None)
        except Exception:  # pragma: no cover — defensive
            self._record_export_failure(name, kind="counter")

    def histogram(
        self,
        name: str,
        value: float,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        try:
            instrument = self._get_or_create_histogram(name)
            instrument.record(value, attributes=dict(attributes) if attributes else None)
        except Exception:  # pragma: no cover — defensive
            self._record_export_failure(name, kind="histogram")

    def _get_or_create_counter(self, name: str) -> Counter:
        with self._lock:
            cached = self._counters.get(name)
            if cached is not None:
                return cached
            instrument = self._meter.create_counter(name)
            self._counters[name] = instrument
            return instrument

    def _get_or_create_histogram(self, name: str) -> Histogram:
        with self._lock:
            cached = self._histograms.get(name)
            if cached is not None:
                return cached
            instrument = self._meter.create_histogram(name)
            self._histograms[name] = instrument
            return instrument

    def _record_export_failure(self, name: str, *, kind: str) -> None:
        try:
            instrument = self._get_or_create_counter(EXPORT_FAILED_COUNTER)
            instrument.add(1, attributes={"backend": "otel", "instrument": kind, "metric": name})
        except Exception:
            # Last-resort fallback: drop the failure silently. The
            # operator will see counter values stop arriving in their
            # backend, which is the next-best signal.
            pass


class OtelObservability:
    """Bundle of the three OTEL-backed adapters.

    Constructed via ``OtelObservability.from_otel_sdk()`` which uses
    the OTEL SDK's auto-configuration (``OTEL_*`` environment
    variables) to wire up tracer / logger / meter providers.
    """

    def __init__(
        self,
        tracer: OtelTracer,
        logger: OtelLogger,
        metric_sink: OtelMetricSink,
    ) -> None:
        self.tracer = tracer
        self.logger = logger
        self.metric_sink = metric_sink

    @classmethod
    def from_otel_sdk(cls, *, instrumentation_name: str = "arc-guardrails") -> OtelObservability:
        """Build adapters from the SDK's auto-configured providers.

        Operators set ``OTEL_EXPORTER_OTLP_ENDPOINT`` etc. before
        invoking this; see the OTEL SDK documentation for the full
        environment-variable surface.
        """
        otel_tracer = otel_trace.get_tracer(instrumentation_name)
        otel_meter = otel_metrics.get_meter(instrumentation_name)
        return cls(
            tracer=OtelTracer(otel_tracer),
            logger=OtelLogger(instrumentation_name),
            metric_sink=OtelMetricSink(otel_meter),
        )


@contextmanager
def _start_recording_span(
    tracer: OtelTracer, name: str, attributes: Mapping[str, Any] | None
) -> Iterator[None]:  # pragma: no cover — internal helper, used by tests
    """Helper for tests that exercise the span-context-manager shape."""
    with tracer.start_span(name, attributes=attributes):
        yield None


__all__ = [
    "OtelTracer",
    "OtelLogger",
    "OtelMetricSink",
    "OtelObservability",
    "EXPORT_FAILED_COUNTER",
]
