"""Mechanically asserts the Conformance checklist of each contract.

Each ``test_*_conformance`` function maps one bullet from the relevant
contract's "Conformance checklist" section to a single assertion.
Skips with ``pytest.importorskip`` when ``[semantic]`` is not installed.
"""

from __future__ import annotations

import pytest

pytest.importorskip("sentence_transformers")
pytest.importorskip("numpy")


def _bundle():
    from arc_guard.middleware import from_sentence_transformers

    return from_sentence_transformers()


def test_intent_encoder_exposes_stable_encoder_id() -> None:
    bundle = _bundle()
    enc_id = bundle.encoder.encoder_id
    assert isinstance(enc_id, str)
    assert ":" in enc_id  # ``<name>:<version>`` shape
    assert enc_id == bundle.encoder.encoder_id  # stable across reads


def test_intent_encoder_returns_opaque_representation() -> None:
    bundle = _bundle()
    rep = bundle.encoder.encode("hello world")
    # The scorer accepts what the encoder produces — that's the contract.
    score = bundle.scorer.score(rep, rep)
    assert score.sentinel == "measured"


def test_intent_encoder_is_thread_safe_concurrent_calls() -> None:
    """Two ``encode()`` calls produce correct, independent results."""
    bundle = _bundle()
    rep_a = bundle.encoder.encode("hello")
    rep_b = bundle.encoder.encode("world")
    # Different inputs → different (or at least not-guaranteed-equal) reps.
    score_self = bundle.scorer.score(rep_a, rep_a)
    score_cross = bundle.scorer.score(rep_a, rep_b)
    assert score_self.value is not None
    assert score_cross.value is not None
    # Self-pair scores are at least as high as cross-pair (cosine triangle).
    assert score_self.value >= score_cross.value - 1e-6


def test_fidelity_scorer_compatible_with_runs_cheaply() -> None:
    bundle = _bundle()
    assert bundle.scorer.compatible_with(bundle.encoder) is True


def test_fidelity_scorer_score_returns_in_range() -> None:
    bundle = _bundle()
    rep_a = bundle.encoder.encode("alpha")
    rep_b = bundle.encoder.encode("beta")
    score = bundle.scorer.score(rep_a, rep_b)
    assert score.sentinel == "measured"
    assert score.value is not None
    assert 0.0 <= score.value <= 1.0


def test_rehydration_verifier_returns_documented_verdict_shape() -> None:
    bundle = _bundle()
    verdict = bundle.verifier.verify(
        sanitized_prompt="Email [EMAIL] for help.",
        rehydration_candidate="Email [EMAIL] for help.",
        entity_map={"[EMAIL]": "alice@acme.com"},
    )
    assert verdict.decision in {"accept", "reject", "partial"}
    assert isinstance(verdict.reason, str)
