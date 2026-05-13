"""Unit tests for the metric helpers in ``arc_guard.evaluation.metrics``."""

from __future__ import annotations

import pytest
from arc_guard_core.evaluation import CorpusEntry

from arc_guard.evaluation.metrics import (
    category_precision_recall,
    compute_fidelity_score_median,
    compute_intelligibility_score,
    compute_latency_percentiles,
    compute_refusal_clarification_rates,
)


def _entry(category: str) -> CorpusEntry:
    """Synthesize a minimal CorpusEntry for the given category."""
    return CorpusEntry(
        category=category,  # type: ignore[arg-type]
        prompt="x",
        turns=None,
        expected_outcomes={"raw": "pass"},
        notes="n",
    )


def test_category_precision_recall_perfect() -> None:
    samples = [
        (_entry("single_turn_jailbreak"), "refuse", "refuse"),
        (_entry("single_turn_jailbreak"), "refuse", "refuse"),
        (_entry("single_turn_jailbreak"), "refuse", "refuse"),
    ]
    p, r = category_precision_recall(samples, "single_turn_jailbreak")
    assert p == 1.0
    assert r == 1.0


def test_category_precision_recall_perfect_negative() -> None:
    """Pass on every benign entry → no positives → both rates 0."""
    samples = [
        (_entry("benign"), "pass", "pass"),
        (_entry("benign"), "pass", "pass"),
    ]
    p, r = category_precision_recall(samples, "benign")
    assert p == 0.0
    assert r == 0.0


def test_category_precision_recall_partial() -> None:
    """2 TP, 1 FP, 1 FN → precision 2/3, recall 2/3."""
    samples = [
        (_entry("single_turn_jailbreak"), "refuse", "refuse"),  # TP
        (_entry("single_turn_jailbreak"), "refuse", "refuse"),  # TP
        (_entry("single_turn_jailbreak"), "refuse", "pass"),  # FP
        (_entry("single_turn_jailbreak"), "pass", "refuse"),  # FN
    ]
    p, r = category_precision_recall(samples, "single_turn_jailbreak")
    assert p == pytest.approx(2 / 3)
    assert r == pytest.approx(2 / 3)


def test_category_precision_recall_filters_to_category() -> None:
    samples = [
        (_entry("single_turn_jailbreak"), "refuse", "refuse"),  # TP for jailbreak
        (_entry("benign"), "refuse", "pass"),  # FP for benign — NOT counted
    ]
    p, r = category_precision_recall(samples, "single_turn_jailbreak")
    # Only the jailbreak entry counts.
    assert p == 1.0
    assert r == 1.0


def test_refusal_clarification_rates() -> None:
    actuals = ["pass", "refuse", "clarify", "warn", "pass", "refuse"]
    refusal, clarification = compute_refusal_clarification_rates(actuals)  # type: ignore[arg-type]
    assert refusal == pytest.approx(2 / 6)
    assert clarification == pytest.approx(1 / 6)


def test_latency_percentiles_basic() -> None:
    p50, p99 = compute_latency_percentiles([1.0, 2.0, 3.0, 4.0, 5.0])
    assert p50 == 3.0
    assert p99 == 5.0


def test_latency_percentiles_empty() -> None:
    p50, p99 = compute_latency_percentiles([])
    assert p50 == 0.0
    assert p99 == 0.0


def test_fidelity_score_median_with_nones() -> None:
    assert compute_fidelity_score_median([0.5, 0.7, None, 0.9]) == 0.7


def test_fidelity_score_median_all_nones_returns_none() -> None:
    assert compute_fidelity_score_median([None, None, None]) is None


def test_intelligibility_score_default_heuristic() -> None:
    answers = [
        "Sure, the weather is sunny.",
        "",  # empty — counts as unintelligible
        "blocked by policy",  # refusal template
        "Please rephrase your question",  # clarification template
        "Here is your translation: hello",
    ]
    prompts = ["a", "b", "c", "d", "e"]
    score = compute_intelligibility_score(answers, prompts)
    assert score == pytest.approx(2 / 5)


def test_intelligibility_score_with_custom_hook() -> None:
    answers = ["yes", "no", "yes"]
    prompts = ["q1", "q2", "q3"]
    score = compute_intelligibility_score(
        answers,
        prompts,
        hook=lambda p, a: a == "yes",
    )
    assert score == pytest.approx(2 / 3)


def test_intelligibility_score_mismatched_lengths_raises() -> None:
    with pytest.raises(ValueError, match="same length"):
        compute_intelligibility_score(["a", "b"], ["x"])
