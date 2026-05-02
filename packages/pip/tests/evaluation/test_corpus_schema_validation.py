"""Every entry in the bundled corpus passes the documented schema."""

from __future__ import annotations

from arc_guard_core.evaluation import (
    Configuration,
    CorpusEntry,
    ExpectedOutcome,
)

from arc_guard.evaluation import load_adversarial_corpus


_VALID_CATEGORIES = {
    "benign",
    "privacy_sensitive",
    "single_turn_jailbreak",
    "multi_turn_deception",
    "rehydration_failure",
}

_VALID_CONFIGURATIONS: set[Configuration] = {
    "raw",
    "sanitize_only",
    "sanitize_plus_jailbreak",
    "sanitize_plus_jailbreak_plus_fidelity",
}

_VALID_OUTCOMES: set[ExpectedOutcome] = {"pass", "warn", "clarify", "refuse"}


def test_every_entry_is_a_corpus_entry() -> None:
    for entry in load_adversarial_corpus():
        assert isinstance(entry, CorpusEntry)


def test_every_entry_has_valid_category() -> None:
    for entry in load_adversarial_corpus():
        assert entry.category in _VALID_CATEGORIES


def test_every_entry_has_exactly_one_of_prompt_or_turns() -> None:
    for entry in load_adversarial_corpus():
        has_prompt = entry.prompt is not None
        has_turns = entry.turns is not None
        assert has_prompt != has_turns, (
            f"entry must have exactly one of prompt or turns: {entry.notes!r}"
        )


def test_every_entry_has_non_empty_notes() -> None:
    for entry in load_adversarial_corpus():
        assert entry.notes


def test_every_entry_has_documented_configurations_only() -> None:
    for entry in load_adversarial_corpus():
        for config in entry.expected_outcomes:
            assert config in _VALID_CONFIGURATIONS


def test_every_entry_has_valid_expected_outcomes() -> None:
    for entry in load_adversarial_corpus():
        assert entry.expected_outcomes
        for outcome in entry.expected_outcomes.values():
            assert outcome in _VALID_OUTCOMES


def test_multi_turn_entries_have_turns_populated() -> None:
    for entry in load_adversarial_corpus():
        if entry.category == "multi_turn_deception":
            assert entry.turns is not None
            assert len(entry.turns) >= 2  # multi-turn means ≥ 2 turns
