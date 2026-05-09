"""Every run that completes generation carries a measured FidelityScore."""

from __future__ import annotations

import hashlib

import pytest
from arc_guard_core.fidelity import FidelityScore
from arc_guard_core.protocols.intent_encoder import (
    IntentEncoder,
    IntentRepresentation,
)
from arc_guard_core.types import GuardInput

from arc_guard.pipeline import GuardPipeline


class _StubSemanticEncoder:
    """Hash-based stub encoder. Same text → same representation."""

    @property
    def encoder_id(self) -> str:
        return "stub-semantic:1"

    def encode(self, text: str) -> IntentRepresentation:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class _StubCosineScorer:
    """Returns 1.0 when reps match exactly, partial when they share a prefix."""

    def compatible_with(self, encoder: IntentEncoder) -> bool:
        return encoder.encoder_id.startswith("stub-semantic:")

    def score(
        self,
        intent: IntentRepresentation,
        answer: IntentRepresentation,
    ) -> FidelityScore:
        if intent == answer:
            return FidelityScore.measured(1.0)
        if isinstance(intent, str) and isinstance(answer, str):
            common = sum(1 for a, b in zip(intent, answer) if a == b)
            return FidelityScore.measured(common / max(len(intent), 1))
        return FidelityScore.measured(0.0)


@pytest.mark.asyncio
async def test_every_completed_run_has_a_measured_fidelity_score() -> None:
    pipeline = GuardPipeline(
        inspectors=[],
        intent_encoder=_StubSemanticEncoder(),
        fidelity_scorer=_StubCosineScorer(),
    )

    inputs = [f"benign question number {i}" for i in range(30)]
    for text in inputs:
        result = await pipeline.pre_process(GuardInput(text=text))
        assert result.fidelity_score is not None
        assert result.fidelity_score.sentinel == "measured"
        assert result.fidelity_score.value is not None
        assert 0.0 <= result.fidelity_score.value <= 1.0


@pytest.mark.asyncio
async def test_completed_run_with_identical_text_scores_one_zero() -> None:
    """Same text → same representation → cosine ≈ 1.0 (perfect alignment)."""
    pipeline = GuardPipeline(
        inspectors=[],
        intent_encoder=_StubSemanticEncoder(),
        fidelity_scorer=_StubCosineScorer(),
    )
    result = await pipeline.pre_process(GuardInput(text="echo this verbatim"))
    assert result.fidelity_score is not None
    assert result.fidelity_score.sentinel == "measured"
    # Pipeline doesn't transform the text on the null path, so intent ==
    # answer and the stub scorer returns 1.0.
    assert result.fidelity_score.value == 1.0
