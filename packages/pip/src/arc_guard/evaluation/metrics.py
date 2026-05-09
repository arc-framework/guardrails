"""Per-configuration metric computation for the evaluation harness.

Each helper takes a list of ``(entry, actual_outcome, expected_outcome)``
triples (or other simple inputs) and returns a tuple or float in the
documented range. The harness composes these into a
``ConfigurationMetrics`` row.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable, Iterable, Sequence
from typing import Final

from arc_guard_core.evaluation import (
    CorpusCategory,
    CorpusEntry,
    ExpectedOutcome,
)

# A "positive" outcome means the configuration produced an action class
# that REACTED to the prompt (warn / clarify / refuse). A "negative"
# outcome is "pass" (no reaction). Per-category precision/recall is
# computed by treating reactions on entries of that category as the
# relevant population.
_REACTION_OUTCOMES: Final[frozenset[ExpectedOutcome]] = frozenset(
    {
        "warn",
        "clarify",
        "refuse",
    }
)


def _is_reaction(outcome: ExpectedOutcome) -> bool:
    return outcome in _REACTION_OUTCOMES


def _precision_recall(
    samples: Iterable[tuple[ExpectedOutcome, ExpectedOutcome]],
) -> tuple[float, float]:
    """Compute (precision, recall) over (actual, expected) outcome pairs.

    Treats reaction outcomes (warn/clarify/refuse) as positives and
    "pass" as negatives. Returns ``(0.0, 0.0)`` when there are no
    relevant samples (avoids division-by-zero and matches "no signal"
    semantics).
    """
    tp = fp = fn = 0
    for actual, expected in samples:
        actual_pos = _is_reaction(actual)
        expected_pos = _is_reaction(expected)
        if actual_pos and expected_pos:
            tp += 1
        elif actual_pos and not expected_pos:
            fp += 1
        elif not actual_pos and expected_pos:
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return precision, recall


def category_precision_recall(
    samples: Sequence[tuple[CorpusEntry, ExpectedOutcome, ExpectedOutcome]],
    category: CorpusCategory,
) -> tuple[float, float]:
    """Compute per-category precision and recall.

    ``samples`` is a list of ``(entry, actual_outcome, expected_outcome)``
    triples. Restricts to entries with the given ``category``. Treats
    reaction outcomes (warn/clarify/refuse) as positives and "pass" as
    negatives.
    """
    pairs = [
        (actual, expected) for entry, actual, expected in samples if entry.category == category
    ]
    return _precision_recall(pairs)


def compute_refusal_clarification_rates(
    actuals: Iterable[ExpectedOutcome],
) -> tuple[float, float]:
    """Compute (refusal_rate, clarification_rate) over a sequence of actuals."""
    actuals_list = list(actuals)
    if not actuals_list:
        return 0.0, 0.0
    refusals = sum(1 for a in actuals_list if a == "refuse")
    clarifications = sum(1 for a in actuals_list if a == "clarify")
    return refusals / len(actuals_list), clarifications / len(actuals_list)


def compute_latency_percentiles(
    latency_ms_samples: Sequence[float],
) -> tuple[float, float]:
    """Compute (p50, p99) over millisecond latency samples.

    Returns ``(0.0, 0.0)`` for an empty input. Uses median for p50; p99
    is computed as the value at the 99th-percentile rank.
    """
    if not latency_ms_samples:
        return 0.0, 0.0
    sorted_samples = sorted(latency_ms_samples)
    p50 = statistics.median(sorted_samples)
    p99_index = max(0, min(len(sorted_samples) - 1, int(0.99 * len(sorted_samples))))
    p99 = sorted_samples[p99_index]
    return float(p50), float(p99)


def compute_fidelity_score_median(
    scores: Iterable[float | None],
) -> float | None:
    """Return median of measured scores; ``None`` when no measured scores present."""
    measured = [s for s in scores if s is not None]
    if not measured:
        return None
    return float(statistics.median(measured))


def compute_intelligibility_score(
    answers: Sequence[str],
    prompts: Sequence[str],
    *,
    hook: Callable[[str, str], bool] | None = None,
) -> float:
    """Per-configuration intelligibility score.

    With ``hook=None``: applies the documented bundled-corpus heuristic —
    per-entry boolean "answer is non-empty AND not solely a refusal /
    clarification template" averaged across runs.

    With ``hook`` supplied: calls ``hook(prompt, answer) -> bool`` for
    each pair and averages.

    Returns ``0.0`` for an empty input.
    """
    if not answers:
        return 0.0
    if len(answers) != len(prompts):
        raise ValueError("answers and prompts must have the same length")
    if hook is not None:
        positives = sum(
            1 for prompt, answer in zip(prompts, answers, strict=True) if hook(prompt, answer)
        )
        return positives / len(answers)
    positives = sum(
        1
        for answer in answers
        if answer and "blocked" not in answer.lower() and "rephrase" not in answer.lower()
    )
    return positives / len(answers)


__all__ = [
    "category_precision_recall",
    "compute_refusal_clarification_rates",
    "compute_latency_percentiles",
    "compute_fidelity_score_median",
    "compute_intelligibility_score",
]
