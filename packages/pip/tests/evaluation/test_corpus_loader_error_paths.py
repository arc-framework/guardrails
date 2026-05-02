"""Loader error paths: malformed corpora raise typed exceptions."""

from __future__ import annotations

from pathlib import Path

import pytest

from arc_guard_core.exceptions import CorpusValidationError

from arc_guard.evaluation import load_adversarial_corpus


def test_missing_corpus_symbol_raises_schema_mismatch(tmp_path: Path) -> None:
    bad = tmp_path / "no_corpus_symbol.py"
    bad.write_text("# no CORPUS symbol\n", encoding="utf-8")
    with pytest.raises(CorpusValidationError) as exc_info:
        load_adversarial_corpus(bad)
    assert exc_info.value.code == "corpus.schema_mismatch"


def test_empty_corpus_raises_corpus_empty(tmp_path: Path) -> None:
    bad = tmp_path / "empty_corpus.py"
    bad.write_text("CORPUS = ()\n", encoding="utf-8")
    with pytest.raises(CorpusValidationError) as exc_info:
        load_adversarial_corpus(bad)
    assert exc_info.value.code == "corpus.empty"


def test_non_corpus_entry_raises_entry_invalid(tmp_path: Path) -> None:
    bad = tmp_path / "wrong_type.py"
    bad.write_text(
        "CORPUS = ('not a CorpusEntry', 'still not one')\n",
        encoding="utf-8",
    )
    with pytest.raises(CorpusValidationError) as exc_info:
        load_adversarial_corpus(bad)
    assert exc_info.value.code == "corpus.entry_invalid"
    # Errors should list ALL offending entries (curators fix in one pass).
    assert "errors" in exc_info.value.details
    errors = exc_info.value.details["errors"]
    assert len(errors) == 2


def test_nonexistent_path_raises_schema_mismatch(tmp_path: Path) -> None:
    nonexistent = tmp_path / "does_not_exist.py"
    with pytest.raises(CorpusValidationError) as exc_info:
        load_adversarial_corpus(nonexistent)
    assert exc_info.value.code == "corpus.schema_mismatch"


def test_corpus_entry_post_init_rejects_both_prompt_and_turns() -> None:
    """Entry with both prompt AND turns raises at construction time."""
    from arc_guard_core.evaluation import CorpusEntry

    with pytest.raises(ValueError, match="exactly one"):
        CorpusEntry(
            category="benign",
            prompt="this",
            turns=("and", "this"),
            expected_outcomes={"raw": "pass"},
            notes="invalid",
        )


def test_corpus_entry_post_init_rejects_neither_prompt_nor_turns() -> None:
    """Entry with neither prompt NOR turns raises at construction time."""
    from arc_guard_core.evaluation import CorpusEntry

    with pytest.raises(ValueError, match="exactly one"):
        CorpusEntry(
            category="benign",
            prompt=None,
            turns=None,
            expected_outcomes={"raw": "pass"},
            notes="invalid",
        )
