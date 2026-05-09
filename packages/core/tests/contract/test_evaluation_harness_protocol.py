"""Structural-conformance tests for the ``EvaluationHarness`` Protocol."""

from __future__ import annotations

from collections.abc import Iterable

from arc_guard_core.evaluation import (
    Configuration,
    ConfigurationMetrics,
    CorpusEntry,
    EvaluationReport,
)
from arc_guard_core.protocols import EvaluationHarness


def _stub_metrics(configuration: Configuration) -> ConfigurationMetrics:
    return ConfigurationMetrics(
        configuration=configuration,
        jailbreak_precision=1.0,
        jailbreak_recall=1.0,
        deception_precision=1.0,
        deception_recall=1.0,
        sanitization_precision=1.0,
        sanitization_recall=1.0,
        fidelity_score_median=None,
        refusal_rate=0.0,
        clarification_rate=0.0,
        latency_p50_ms=0.5,
        latency_p99_ms=1.0,
        intelligibility_score=1.0,
    )


class _StubHarness:
    def evaluate(
        self,
        corpus: Iterable[CorpusEntry],
        configurations: tuple[Configuration, ...],
        *,
        seed: int = 0,
    ) -> EvaluationReport:
        corpus_list = list(corpus)
        return EvaluationReport(
            seed=seed,
            corpus_size=len(corpus_list),
            configurations=tuple(_stub_metrics(c) for c in configurations),
        )


def test_evaluation_harness_is_runtime_checkable() -> None:
    assert isinstance(_StubHarness(), EvaluationHarness)


def test_evaluate_returns_report_with_one_row_per_configuration() -> None:
    harness = _StubHarness()
    report = harness.evaluate(
        corpus=[],
        configurations=("raw", "sanitize_only"),
        seed=0,
    )
    assert report.seed == 0
    assert report.corpus_size == 0
    assert len(report.configurations) == 2
    assert report.configurations[0].configuration == "raw"
    assert report.configurations[1].configuration == "sanitize_only"


def test_evaluate_is_reproducible_for_same_seed() -> None:
    harness = _StubHarness()
    r1 = harness.evaluate(corpus=[], configurations=("raw",), seed=42)
    r2 = harness.evaluate(corpus=[], configurations=("raw",), seed=42)
    assert r1.configurations[0] == r2.configurations[0]
