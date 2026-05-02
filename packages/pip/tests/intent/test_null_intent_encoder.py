"""``NullIntentEncoder`` + ``NullFidelityScorer`` unit tests."""

from __future__ import annotations

from arc_guard_core.fidelity import NOT_MEASURED

from arc_guard.fidelity.scorer import NullFidelityScorer
from arc_guard.intent.capture import NULL_INTENT_REPRESENTATION, NullIntentEncoder


def test_null_encoder_id_is_stable() -> None:
    encoder = NullIntentEncoder()
    assert encoder.encoder_id == "null:1"
    assert encoder.encoder_id == NullIntentEncoder().encoder_id


def test_null_encode_returns_singleton_marker() -> None:
    encoder = NullIntentEncoder()
    rep = encoder.encode("hello world")
    assert rep is NULL_INTENT_REPRESENTATION
    # Same input produces the same representation across calls.
    assert encoder.encode("hello world") is encoder.encode("anything else")


def test_null_scorer_compatible_with_null_encoder() -> None:
    scorer = NullFidelityScorer()
    assert scorer.compatible_with(NullIntentEncoder()) is True


def test_null_scorer_compatible_with_other_null_id_prefixes() -> None:
    """Operators with their own ``null:...`` encoder ID are accepted."""

    class _OtherNull:
        @property
        def encoder_id(self) -> str:
            return "null:custom-test-7"

        def encode(self, text: str) -> object:
            return None

    scorer = NullFidelityScorer()
    assert scorer.compatible_with(_OtherNull()) is True


def test_null_scorer_incompatible_with_concrete_encoder() -> None:
    class _ConcreteEncoder:
        @property
        def encoder_id(self) -> str:
            return "sentence-transformers/all-MiniLM-L6-v2:1"

        def encode(self, text: str) -> object:
            return [0.0] * 384

    scorer = NullFidelityScorer()
    assert scorer.compatible_with(_ConcreteEncoder()) is False


def test_null_scorer_returns_not_measured() -> None:
    scorer = NullFidelityScorer()
    score = scorer.score(NULL_INTENT_REPRESENTATION, NULL_INTENT_REPRESENTATION)
    assert score == NOT_MEASURED
    assert score.sentinel == "not_measured"
    assert score.value is None
