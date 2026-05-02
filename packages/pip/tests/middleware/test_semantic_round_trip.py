"""End-to-end: SemanticBundle.from_sentence_transformers → encode → score."""

from __future__ import annotations

import pytest

pytest.importorskip("sentence_transformers")
pytest.importorskip("numpy")


def test_semantic_bundle_round_trip_produces_measured_score() -> None:
    from arc_guard.middleware.semantic import SemanticBundle

    bundle = SemanticBundle.from_sentence_transformers()
    rep_a = bundle.encoder.encode("the cat sat on the mat")
    rep_b = bundle.encoder.encode("a feline rested on a rug")
    score = bundle.scorer.score(rep_a, rep_b)
    assert score.sentinel == "measured"
    assert score.value is not None
    assert 0.0 <= score.value <= 1.0
    # Synonymous sentences should score reasonably high.
    assert score.value >= 0.4


def test_protocols_are_runtime_checkable_against_canned_classes() -> None:
    from arc_guard_core.protocols import (
        FidelityScorer,
        IntentEncoder,
        RehydrationVerifier,
    )

    from arc_guard.middleware.semantic import SemanticBundle

    bundle = SemanticBundle.from_sentence_transformers()
    assert isinstance(bundle.encoder, IntentEncoder)
    assert isinstance(bundle.scorer, FidelityScorer)
    assert isinstance(bundle.verifier, RehydrationVerifier)
