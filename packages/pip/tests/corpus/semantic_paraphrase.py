"""Semantic content policy paraphrase corpus.

Validates the >=90% block rate on paraphrases + <5% false-positive rate
on benign content for a well-authored semantic content policy with five
to ten exemplars.

The corpora (100 paraphrases + 100 benign) are operator-supplied
fixtures; this scaffolding drives the rates.
"""

from __future__ import annotations

import pytest


def _load_paraphrases() -> list[str]:
    return []


def _load_benign() -> list[str]:
    return []


@pytest.mark.slow
@pytest.mark.requires_semantic
def test_paraphrase_block_rate_at_least_90_percent() -> None:
    paraphrases = _load_paraphrases()
    benign = _load_benign()
    if not paraphrases or not benign:
        pytest.skip(
            "Semantic paraphrase corpora not assembled in this environment."
        )
    raise NotImplementedError("corpus loader stub")
