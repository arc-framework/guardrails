"""Held-out PII corpus: zero decision drift between explicit-strategy
and selector-driven forms.

This is the validation test for the "operator can swap `strategy:` for
`selector: default` without changing decision behavior" success
criterion. Requires a 200-request representative PII corpus assembled
from real production-shape inputs.

The corpus assembly is a separate operator-supplied artifact (loaded
from a YAML / JSON fixture); the test scaffolding here drives the
comparison loop. Replace `_load_corpus()` with a real fixture loader
when the corpus is curated.
"""

from __future__ import annotations

import pytest


def _load_corpus() -> list[str]:
    """Placeholder: real corpus would load from a fixture file."""
    return []


@pytest.mark.slow
def test_zero_decision_drift_on_pii_corpus() -> None:
    corpus = _load_corpus()
    if not corpus:
        pytest.skip(
            "PII corpus not assembled in this environment. "
            "Provide 200 representative requests via _load_corpus to enable."
        )

    # When the corpus exists, drive each request through the pipeline twice:
    # once with explicit strategy: bindings, once with selector: default.
    # Assert GuardResult.transforms is byte-identical.
    raise NotImplementedError(
        "corpus loader stub; provide _load_corpus to enable assertion"
    )
