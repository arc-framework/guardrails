"""Evaluation harness types — corpus entries, per-configuration metrics, report.

Used by the comparative evaluation harness to drive multiple pipeline
configurations against a labeled corpus and emit a reproducible
comparison report.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

Configuration = Literal[
    "raw",
    "sanitize_only",
    "sanitize_plus_jailbreak",
    "sanitize_plus_jailbreak_plus_fidelity",
]

ExpectedOutcome = Literal["pass", "warn", "clarify", "refuse"]

CorpusCategory = Literal[
    "benign",
    "privacy_sensitive",
    "single_turn_jailbreak",
    "multi_turn_deception",
    "rehydration_failure",
]


@dataclass(frozen=True)
class CorpusEntry:
    """One labeled corpus entry.

    Validation rules:

    - exactly one of ``prompt`` or ``turns`` is non-``None``.
    - ``expected_outcomes`` MUST contain at least one ``Configuration`` key.
    - ``notes`` MUST be non-empty.
    """

    category: CorpusCategory
    prompt: str | None
    turns: tuple[str, ...] | None
    expected_outcomes: Mapping[Configuration, ExpectedOutcome]
    notes: str

    def __post_init__(self) -> None:
        if (self.prompt is None) == (self.turns is None):
            raise ValueError(
                "CorpusEntry: exactly one of `prompt` or `turns` must be set "
                "(both populated or both None is invalid)"
            )
        if not self.expected_outcomes:
            raise ValueError(
                "CorpusEntry.expected_outcomes must contain at least one Configuration key"
            )
        if not self.notes:
            raise ValueError("CorpusEntry.notes must be non-empty")


@dataclass(frozen=True)
class ConfigurationMetrics:
    """Per-configuration metric row in the evaluation report.

    Validation rules:

    - precision/recall/rate fields in ``[0.0, 1.0]``.
    - latency fields in milliseconds, ``>= 0``.
    - ``fidelity_score_median`` is ``None`` for configurations that
      don't run the fidelity-verification stage (or when the
      ``[semantic]`` extra is not installed and the harness fell back
      per the documented fallback rule).
    - ``intelligibility_score`` in ``[0.0, 1.0]``; computed by the
      documented heuristic for the bundled corpus, operator-overridable
      via the harness's ``intelligibility_hook`` parameter.
    """

    configuration: Configuration
    jailbreak_precision: float
    jailbreak_recall: float
    deception_precision: float
    deception_recall: float
    sanitization_precision: float
    sanitization_recall: float
    fidelity_score_median: float | None
    refusal_rate: float
    clarification_rate: float
    latency_p50_ms: float
    latency_p99_ms: float
    intelligibility_score: float

    def __post_init__(self) -> None:
        for name in (
            "jailbreak_precision",
            "jailbreak_recall",
            "deception_precision",
            "deception_recall",
            "sanitization_precision",
            "sanitization_recall",
            "refusal_rate",
            "clarification_rate",
            "intelligibility_score",
        ):
            value = getattr(self, name)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"ConfigurationMetrics.{name} must be in [0.0, 1.0]; got {value}")
        if self.latency_p50_ms < 0 or self.latency_p99_ms < 0:
            raise ValueError("ConfigurationMetrics latency fields must be >= 0")
        if self.fidelity_score_median is not None and not (
            0.0 <= self.fidelity_score_median <= 1.0
        ):
            raise ValueError(
                "ConfigurationMetrics.fidelity_score_median must be in [0.0, 1.0] or None"
            )


@dataclass(frozen=True)
class EvaluationReport:
    """Output of an ``EvaluationHarness.evaluate`` invocation."""

    seed: int
    corpus_size: int
    configurations: tuple[ConfigurationMetrics, ...]

    def __post_init__(self) -> None:
        if self.corpus_size < 0:
            raise ValueError(f"EvaluationReport.corpus_size must be >= 0; got {self.corpus_size}")
        if not self.configurations:
            raise ValueError("EvaluationReport.configurations must be non-empty")


__all__ = [
    "Configuration",
    "ExpectedOutcome",
    "CorpusCategory",
    "CorpusEntry",
    "ConfigurationMetrics",
    "EvaluationReport",
]
