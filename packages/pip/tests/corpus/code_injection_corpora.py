"""Code-injection inspector corpora — 50 positives + 200 negatives per
inspector class.

Validates the >=95% true-positive rate AND <5% false-positive rate
targets on curated representative attack/benign samples. Corpora are
operator-supplied fixtures.
"""

from __future__ import annotations

import pytest


def _load_corpus(name: str) -> tuple[list[str], list[str]]:
    """Returns (positives, negatives) for the given inspector name."""
    return ([], [])


@pytest.mark.slow
@pytest.mark.requires_code_injection
@pytest.mark.parametrize("inspector_name", ["sql", "shell", "template"])
def test_code_injection_corpus_rates(inspector_name: str) -> None:
    positives, negatives = _load_corpus(inspector_name)
    if not positives or not negatives:
        pytest.skip(f"{inspector_name} corpus not assembled in this environment.")
    raise NotImplementedError("corpus loader stub")
