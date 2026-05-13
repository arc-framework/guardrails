"""Post-decision sampling and log-level-floor wrappers.

Three pieces:

- ``BufferedTracer`` and ``BufferedLogger`` accumulate spans + events
  during a run. At run end the pipeline calls ``flush_or_discard()``
  with the run's sampling decision; emissions either replay to the
  underlying real sinks or are dropped.
- ``LogLevelFloorLogger`` enforces ``ObservabilityConfig.log_level_floor``:
  events whose level is below the floor are suppressed, except for
  failure events which always pass through at their natural level.
- ``RunSampler`` is a per-run helper that the pipeline constructs at
  run entry; it bundles the buffered tracer + floor-aware logger and
  knows how to commit / discard at end of run.

Metrics are intentionally not buffered: the spec calls out that
metrics always emit regardless of sampling. The metric sink passes
through unchanged.
"""

from __future__ import annotations

import random
import threading
from collections.abc import Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from typing import Any

from arc_guard_core.observability import Logger, MetricSink, Tracer
from arc_guard_core.observability_config import LogLevelFloor, ObservabilityConfig

# Severity ordering. Events at or above the floor emit; events below
# the floor are suppressed (unless they're failure events).
_LEVEL_ORDER: dict[str, int] = {
    "debug": 10,
    "info": 20,
    "warn": 30,
    "warning": 30,
    "error": 40,
    "critical": 50,
}

# Failure events always pass through the level floor — they're the
# whole point of having observability.
_FAILURE_EVENT_NAMES = frozenset(
    {
        "guard.stage.failed",
        "guard.request.rejected",
        "guard.observability.export_failed",
        "guard.observability.attribute_dropped",
    }
)

# Counter name for runs whose buffered emissions were dropped by
# sampling — operators can subtract this from total runs to detect
# unexpected sampling rates.
SPAN_DROPPED_COUNTER = "arc_guardrails.observability.span_dropped"


@dataclass
class _PendingSpan:
    """One captured span that hasn't been replayed yet."""

    name: str
    attributes: dict[str, Any]
    children: list[_PendingSpan] = field(default_factory=list)


@dataclass
class _PendingEvent:
    """One captured log event that hasn't been replayed yet."""

    name: str
    level: str
    fields: dict[str, Any]


class BufferedTracer:
    """Captures spans during a run; replays to a real tracer on flush.

    Spans are recorded as nested ``_PendingSpan`` records so the parent
    / child relationship is preserved when replayed. The replay calls
    the underlying real tracer's ``start_span`` with the same name +
    attributes, so any backend that cares about parent-child context
    (e.g. OTEL) sees the same shape it would have seen if buffering
    were absent.
    """

    def __init__(self, real_tracer: Tracer) -> None:
        self._real = real_tracer
        self._lock = threading.Lock()
        self._roots: list[_PendingSpan] = []
        self._stack: list[_PendingSpan] = []

    def start_span(
        self, name: str, *, attributes: Mapping[str, Any] | None = None
    ) -> AbstractContextManager[Any]:
        attrs = dict(attributes) if attributes else {}
        return self._span_cm(name, attrs)

    @contextmanager
    def _span_cm(self, name: str, attrs: dict[str, Any]) -> Iterator[None]:
        pending = _PendingSpan(name=name, attributes=attrs)
        with self._lock:
            if self._stack:
                self._stack[-1].children.append(pending)
            else:
                self._roots.append(pending)
            self._stack.append(pending)
        try:
            yield None
        finally:
            with self._lock:
                if self._stack and self._stack[-1] is pending:
                    self._stack.pop()

    def flush_to(self, real_tracer: Tracer | None = None) -> None:
        """Replay buffered spans into the underlying tracer."""
        target = real_tracer or self._real
        with self._lock:
            roots = list(self._roots)
            self._roots.clear()
            self._stack.clear()
        for span in roots:
            self._replay(target, span)

    def _replay(self, target: Tracer, span: _PendingSpan) -> None:
        with target.start_span(span.name, attributes=span.attributes):
            for child in span.children:
                self._replay(target, child)

    def discard(self) -> None:
        """Drop buffered spans without replaying."""
        with self._lock:
            self._roots.clear()
            self._stack.clear()


class BufferedLogger:
    """Captures log events during a run; replays on flush.

    Events whose name appears in ``_FAILURE_EVENT_NAMES`` are also
    forwarded to the underlying logger immediately so failures are
    visible even when the run gets sampled out.
    """

    def __init__(self, real_logger: Logger, *, bound: Mapping[str, Any] | None = None) -> None:
        self._real = real_logger
        self._lock = threading.Lock()
        self._buffer: list[_PendingEvent] = []
        self._bound: dict[str, Any] = dict(bound) if bound else {}

    def bind(self, **fields: Any) -> BufferedLogger:
        merged = {**self._bound, **fields}
        bound = BufferedLogger(self._real, bound=merged)
        # Share buffer + lock with parent so flush sees all events.
        bound._buffer = self._buffer
        bound._lock = self._lock
        return bound

    def event(self, name: str, *, level: str = "info", **fields: Any) -> None:
        merged: dict[str, Any] = {**self._bound, **fields}
        with self._lock:
            self._buffer.append(_PendingEvent(name=name, level=level, fields=merged))
        # Failure events pass through immediately so they're visible
        # even when the run gets sampled out.
        if name in _FAILURE_EVENT_NAMES:
            self._real.event(name, level=level, **merged)

    def flush_to(self, real_logger: Logger | None = None) -> None:
        target = real_logger or self._real
        with self._lock:
            buffered = list(self._buffer)
            self._buffer.clear()
        for event in buffered:
            if event.name in _FAILURE_EVENT_NAMES:
                # Already forwarded immediately; do not double-emit.
                continue
            target.event(event.name, level=event.level, **event.fields)

    def discard(self) -> None:
        with self._lock:
            self._buffer.clear()


class LogLevelFloorLogger:
    """Suppresses stage-transition events below the configured floor.

    Wraps any ``Logger``. Events at or above the floor pass through.
    Events below the floor are dropped — UNLESS they are failure
    events, which always pass through at their natural level (the
    failure-event bypass is the contract requirement).
    """

    def __init__(self, real_logger: Logger, *, floor: LogLevelFloor) -> None:
        self._real = real_logger
        self._floor_value = _LEVEL_ORDER.get(floor.lower(), _LEVEL_ORDER["info"])
        self._floor_name: LogLevelFloor = floor

    def bind(self, **fields: Any) -> LogLevelFloorLogger:
        bound_real = self._real.bind(**fields)
        return LogLevelFloorLogger(bound_real, floor=self._floor_name)

    def event(self, name: str, *, level: str = "info", **fields: Any) -> None:
        if name in _FAILURE_EVENT_NAMES:
            self._real.event(name, level=level, **fields)
            return
        level_value = _LEVEL_ORDER.get(level.lower(), _LEVEL_ORDER["info"])
        if level_value < self._floor_value:
            return
        self._real.event(name, level=level, **fields)


@dataclass
class RunSampler:
    """Per-run sampling state.

    Constructed at run entry by the pipeline. The buffered sinks
    accumulate spans + events; at run end the pipeline calls
    ``finalize(refusal_present)`` which decides flush vs discard
    based on the sampling rate and the refusal-always-emits config.
    """

    tracer: BufferedTracer
    logger: BufferedLogger
    metric_sink: MetricSink
    sampling_rate: float
    refusal_always_emits: bool
    real_tracer: Tracer
    real_logger: Logger

    def finalize(self, *, refusal_present: bool, correlation_id: str) -> bool:
        """Flush buffered emissions if sampled-in or if refusal forces it.

        Returns True when emissions were flushed, False when dropped.
        """
        keep = self._should_keep(refusal_present=refusal_present)
        if keep:
            self.tracer.flush_to(self.real_tracer)
            self.logger.flush_to(self.real_logger)
            return True
        # Sampled out: discard buffered spans + non-failure events;
        # bump the dropped counter so the rate is auditable.
        self.tracer.discard()
        self.logger.discard()
        self.metric_sink.counter(
            SPAN_DROPPED_COUNTER,
            attributes={"reason": "sampling", "correlation_id": correlation_id},
        )
        return False

    def _should_keep(self, *, refusal_present: bool) -> bool:
        if refusal_present and self.refusal_always_emits:
            return True
        if self.sampling_rate >= 1.0:
            return True
        if self.sampling_rate <= 0.0:
            return False
        return random.random() < self.sampling_rate


def build_run_sampler(
    config: ObservabilityConfig,
    *,
    tracer: Tracer,
    logger: Logger,
    metric_sink: MetricSink,
) -> RunSampler:
    """Construct a per-run sampler from the live observability config.

    The returned ``RunSampler.tracer`` and ``.logger`` should be
    threaded into the per-stage ``stage_runner`` calls in place of
    the raw hooks; the pipeline then calls ``finalize()`` once at run
    end.
    """
    floor_logger = LogLevelFloorLogger(logger, floor=config.log_level_floor)
    buffered_tracer = BufferedTracer(tracer)
    buffered_logger = BufferedLogger(floor_logger)
    return RunSampler(
        tracer=buffered_tracer,
        logger=buffered_logger,
        metric_sink=metric_sink,
        sampling_rate=config.sampling_rate,
        refusal_always_emits=config.refusal_always_emits,
        real_tracer=tracer,
        real_logger=floor_logger,
    )


__all__ = [
    "BufferedTracer",
    "BufferedLogger",
    "LogLevelFloorLogger",
    "RunSampler",
    "build_run_sampler",
    "SPAN_DROPPED_COUNTER",
]
