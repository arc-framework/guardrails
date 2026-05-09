"""Bundled corpus meets the documented size floors."""

from __future__ import annotations

from collections import Counter

from arc_guard.evaluation import load_adversarial_corpus


def test_bundled_corpus_has_at_least_50_entries() -> None:
    corpus = load_adversarial_corpus()
    assert len(corpus) >= 50


def test_bundled_corpus_has_at_least_8_per_category() -> None:
    corpus = load_adversarial_corpus()
    counter = Counter(e.category for e in corpus)
    expected_categories = {
        "benign",
        "privacy_sensitive",
        "single_turn_jailbreak",
        "multi_turn_deception",
        "rehydration_failure",
    }
    assert set(counter) == expected_categories
    for category in expected_categories:
        assert counter[category] >= 8, (
            f"category {category!r} has only {counter[category]} entries; floor is 8"
        )
