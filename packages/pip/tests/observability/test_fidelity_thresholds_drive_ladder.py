"""Non-default thresholds drive the ladder per the configured boundaries."""

from __future__ import annotations

import pytest
from arc_guard_core.fidelity import FidelityScore
from arc_guard_core.observability_config import (
    FidelityThresholds,
    ObservabilityConfig,
)
from arc_guard_core.protocols.intent_encoder import (
    IntentEncoder,
    IntentRepresentation,
)
from arc_guard_core.types import GuardInput

from arc_guard.config_env import GuardConfig
from arc_guard.pipeline import GuardPipeline


class _FixedScoreScorer:
    """Returns a fixed measured value regardless of input."""

    def __init__(self, value: float) -> None:
        self._value = value

    def compatible_with(self, encoder: IntentEncoder) -> bool:
        return encoder.encoder_id.startswith("fixed-stub:")

    def score(
        self,
        intent: IntentRepresentation,
        answer: IntentRepresentation,
    ) -> FidelityScore:
        return FidelityScore.measured(self._value)


class _StubEncoder:
    @property
    def encoder_id(self) -> str:
        return "fixed-stub:1"

    def encode(self, text: str) -> IntentRepresentation:
        return text


@pytest.mark.asyncio
async def test_aggressive_thresholds_promote_above_warn_to_warn_band() -> None:
    """With ``warn=0.85``, a score of 0.75 lands in the warn band."""
    config = GuardConfig(
        observability=ObservabilityConfig(
            fidelity_thresholds=FidelityThresholds(
                warn=0.85,
                clarify=0.6,
                refuse=0.4,
            ),
        ),
    )
    pipeline = GuardPipeline(
        config=config,
        inspectors=[],
        intent_encoder=_StubEncoder(),
        fidelity_scorer=_FixedScoreScorer(0.75),
    )
    result = await pipeline.pre_process(GuardInput(text="hello"))
    assert result.fidelity_warning is True
    assert result.action == "pass"
    assert result.clarification is None
    assert result.refusal is None


@pytest.mark.asyncio
async def test_aggressive_thresholds_promote_warn_score_to_clarify_band() -> None:
    """With ``clarify=0.6``, a score of 0.5 lands in the clarify band."""
    config = GuardConfig(
        observability=ObservabilityConfig(
            fidelity_thresholds=FidelityThresholds(
                warn=0.85,
                clarify=0.6,
                refuse=0.4,
            ),
        ),
    )
    pipeline = GuardPipeline(
        config=config,
        inspectors=[],
        intent_encoder=_StubEncoder(),
        fidelity_scorer=_FixedScoreScorer(0.5),
    )
    result = await pipeline.pre_process(GuardInput(text="hello"))
    assert result.clarification is not None
    assert result.action != "block"
    assert result.fidelity_warning is False


@pytest.mark.asyncio
async def test_default_thresholds_keep_high_score_above_warn() -> None:
    """Default ``warn=0.7`` — a score of 0.9 is above_warn (no change)."""
    pipeline = GuardPipeline(
        inspectors=[],
        intent_encoder=_StubEncoder(),
        fidelity_scorer=_FixedScoreScorer(0.9),
    )
    result = await pipeline.pre_process(GuardInput(text="hello"))
    assert result.fidelity_warning is False
    assert result.action == "pass"
    assert result.clarification is None
    assert result.refusal is None
