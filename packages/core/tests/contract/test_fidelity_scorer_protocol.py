"""Structural-conformance tests for the ``FidelityScorer`` Protocol."""

from __future__ import annotations

from arc_guard_core.fidelity import NOT_MEASURED, FidelityScore
from arc_guard_core.protocols import (
    FidelityScorer,
    IntentEncoder,
    IntentRepresentation,
)


class _StubEncoder:
    @property
    def encoder_id(self) -> str:
        return "stub:1"

    def encode(self, text: str) -> IntentRepresentation:
        return text


class _IncompatibleEncoder:
    @property
    def encoder_id(self) -> str:
        return "other:7"

    def encode(self, text: str) -> IntentRepresentation:
        return text


class _StubScorer:
    def compatible_with(self, encoder: IntentEncoder) -> bool:
        return encoder.encoder_id.startswith("stub:")

    def score(
        self,
        intent: IntentRepresentation,
        answer: IntentRepresentation,
    ) -> FidelityScore:
        if intent == answer:
            return FidelityScore.measured(1.0)
        return FidelityScore.measured(0.5)


def test_fidelity_scorer_is_runtime_checkable() -> None:
    assert isinstance(_StubScorer(), FidelityScorer)


def test_compatible_with_returns_bool() -> None:
    scorer = _StubScorer()
    assert scorer.compatible_with(_StubEncoder()) is True
    assert scorer.compatible_with(_IncompatibleEncoder()) is False


def test_score_returns_fidelity_score_in_range() -> None:
    scorer = _StubScorer()
    out = scorer.score("hello", "hello")
    assert isinstance(out, FidelityScore)
    assert out.sentinel == "measured"
    assert out.value is not None
    assert 0.0 <= out.value <= 1.0


def test_sentinel_round_trips() -> None:
    not_measured = NOT_MEASURED
    assert not_measured.sentinel == "not_measured"
    assert not_measured.value is None
