"""In-memory recording sinks for tests + dependent specs.

Three Protocol implementations (``RecordingTracer``, ``RecordingLogger``,
``RecordingMetricSink``) capture every emission so test harnesses can
assert what the pipeline produced. Lives in production code so
downstream specs (rehydration, jailbreak, eval) can reuse them in their
own test suites without depending on ``arc_guard``'s test sources.

Concurrency: thread-safe via internal ``threading.Lock``.
Failure mode: never raise — observability sinks are non-blocking.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CapturedSpan:
    """One captured span emission."""

    name: str
    attributes: Mapping[str, Any]
    started_at_ns: int
    ended_at_ns: int
    status: str = "ok"

    @property
    def duration_ms(self) -> float:
        return (self.ended_at_ns - self.started_at_ns) / 1_000_000


@dataclass(frozen=True)
class CapturedEvent:
    """One captured structured-log event."""

    name: str
    level: str
    fields: Mapping[str, Any]
    timestamp_ns: int


@dataclass(frozen=True)
class CapturedMetric:
    """One captured metric sample."""

    name: str
    kind: str  # "counter" | "histogram"
    value: float
    attributes: Mapping[str, Any]


@dataclass
class CapturedArtifacts:
    """Bundle of everything a recording session produced.

    Used by the leak scanner and the cross-system join assertions in
    Spec 004's test harnesses.
    """

    spans: list[CapturedSpan] = field(default_factory=list)
    events: list[CapturedEvent] = field(default_factory=list)
    metrics: list[CapturedMetric] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Tracer
# ---------------------------------------------------------------------------


class RecordingTracer:
    """Captures every span as a ``CapturedSpan``.

    Concurrency: thread-safe.
    Failure mode: never raises.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.captured_spans: list[CapturedSpan] = []

    def start_span(
        self, name: str, *, attributes: Mapping[str, Any] | None = None
    ) -> AbstractContextManager[Any]:
        return self._span_cm(name, dict(attributes) if attributes else {})

    @contextmanager
    def _span_cm(self, name: str, attributes: dict[str, Any]) -> Iterator[None]:
        started = time.monotonic_ns()
        status = "ok"
        try:
            yield None
        except BaseException:
            status = "error"
            raise
        finally:
            ended = time.monotonic_ns()
            with self._lock:
                self.captured_spans.append(
                    CapturedSpan(
                        name=name,
                        attributes=attributes,
                        started_at_ns=started,
                        ended_at_ns=ended,
                        status=status,
                    )
                )

    def clear(self) -> None:
        with self._lock:
            self.captured_spans.clear()


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------


class RecordingLogger:
    """Captures every event as a ``CapturedEvent``.

    Concurrency: thread-safe.
    Failure mode: never raises.
    """

    def __init__(self, _bound_fields: Mapping[str, Any] | None = None) -> None:
        self._lock = threading.Lock()
        self._bound: dict[str, Any] = dict(_bound_fields) if _bound_fields else {}
        # Bound loggers share the parent's captured list so the test sees
        # everything regardless of which bound logger fired the event.
        self.captured_events: list[CapturedEvent] = []

    def bind(self, **fields: Any) -> RecordingLogger:
        merged = {**self._bound, **fields}
        new_logger = RecordingLogger(merged)
        # Share the same captured list so tests can read from the root.
        new_logger.captured_events = self.captured_events
        new_logger._lock = self._lock
        return new_logger

    def event(self, name: str, *, level: str = "info", **fields: Any) -> None:
        merged: dict[str, Any] = {**self._bound, **fields}
        ts = time.monotonic_ns()
        with self._lock:
            self.captured_events.append(
                CapturedEvent(name=name, level=level, fields=merged, timestamp_ns=ts)
            )

    def clear(self) -> None:
        with self._lock:
            self.captured_events.clear()


# ---------------------------------------------------------------------------
# Metric sink
# ---------------------------------------------------------------------------


class RecordingMetricSink:
    """Captures every counter / histogram emission as a ``CapturedMetric``.

    Concurrency: thread-safe.
    Failure mode: never raises.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.captured_metrics: list[CapturedMetric] = []

    def counter(
        self,
        name: str,
        value: int = 1,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        attrs = dict(attributes) if attributes else {}
        with self._lock:
            self.captured_metrics.append(
                CapturedMetric(name=name, kind="counter", value=float(value), attributes=attrs)
            )

    def histogram(
        self,
        name: str,
        value: float,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        attrs = dict(attributes) if attributes else {}
        with self._lock:
            self.captured_metrics.append(
                CapturedMetric(name=name, kind="histogram", value=float(value), attributes=attrs)
            )

    def clear(self) -> None:
        with self._lock:
            self.captured_metrics.clear()


__all__ = [
    "CapturedSpan",
    "CapturedEvent",
    "CapturedMetric",
    "CapturedArtifacts",
    "RecordingTracer",
    "RecordingLogger",
    "RecordingMetricSink",
]
