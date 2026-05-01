"""DecisionEmitter calls Logger and MetricSink hooks correctly."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from arc_guard_core.policy import RiskBand, RoutedOutcome
from arc_guard_core.types import GuardResult

from arc_guard.decision.emitter import DecisionEmitter


class _RecordingLogger:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def bind(self, **fields: Any) -> _RecordingLogger:
        return self

    def event(self, name: str, *, level: str = "info", **fields: Any) -> None:
        self.calls.append((name, level, dict(fields)))


class _RecordingMetrics:
    def __init__(self) -> None:
        self.counters: list[tuple[str, int, dict[str, Any]]] = []
        self.histograms: list[tuple[str, float, dict[str, Any]]] = []

    def counter(
        self,
        name: str,
        value: int = 1,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        self.counters.append((name, value, dict(attributes or {})))

    def histogram(
        self,
        name: str,
        value: float,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        self.histograms.append((name, value, dict(attributes or {})))


def test_logger_event_called_once_with_decision_name() -> None:
    emitter = DecisionEmitter()
    result = GuardResult(text="hi", phase="pre_process")
    outcome = RoutedOutcome(
        transformed_text="hi",
        decisions=(),
        aggregate_action="pass",
        aggregate_band=RiskBand.LOW,
    )
    record = emitter.build(result, outcome, latency_ms=0.5)
    logger = _RecordingLogger()
    metrics = _RecordingMetrics()
    emitter.emit(record, logger=logger, metrics=metrics)
    assert len(logger.calls) == 1
    name, level, fields = logger.calls[0]
    assert name == "guard.decision"
    assert level == "info"
    assert fields["aggregate_action"] == "pass"


def test_metrics_counter_and_histogram_called_once() -> None:
    emitter = DecisionEmitter()
    result = GuardResult(text="hi", phase="pre_process")
    outcome = RoutedOutcome(
        transformed_text="hi",
        decisions=(),
        aggregate_action="redact",
        aggregate_band=RiskBand.MEDIUM,
    )
    record = emitter.build(result, outcome, latency_ms=1.0)
    logger = _RecordingLogger()
    metrics = _RecordingMetrics()
    emitter.emit(record, logger=logger, metrics=metrics)

    assert len(metrics.counters) == 1
    counter_name, _, counter_attrs = metrics.counters[0]
    assert counter_name == "guard.decisions"
    assert counter_attrs["action"] == "redact"
    assert counter_attrs["risk_band"] == "medium"

    assert len(metrics.histograms) == 1
    hist_name, _, _ = metrics.histograms[0]
    assert hist_name == "guard.findings_count"


def test_logger_failure_does_not_propagate() -> None:
    """Constitution Principle V: emission MUST NOT raise back to the pipeline."""

    class _BrokenLogger:
        def bind(self, **fields: Any) -> _BrokenLogger:
            return self

        def event(self, name: str, *, level: str = "info", **fields: Any) -> None:
            raise RuntimeError("broken")

    emitter = DecisionEmitter()
    result = GuardResult(text="hi", phase="pre_process")
    outcome = RoutedOutcome(
        transformed_text="hi",
        decisions=(),
        aggregate_action="pass",
        aggregate_band=RiskBand.LOW,
    )
    record = emitter.build(result, outcome, latency_ms=0.0)
    metrics = _RecordingMetrics()
    # Must not raise.
    emitter.emit(record, logger=_BrokenLogger(), metrics=metrics)
