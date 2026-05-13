"""End-to-end smoke: intent fidelity + rehydration pipeline wiring."""

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


class _StubEncoder:
    @property
    def encoder_id(self) -> str:
        return "smoke-stub:1"

    def encode(self, text: str) -> IntentRepresentation:
        return text


class _MeasuringScorer:
    """Returns score 0.95 for any input (above_warn)."""

    def compatible_with(self, encoder: IntentEncoder) -> bool:
        return encoder.encoder_id.startswith("smoke-stub:")

    def score(
        self,
        intent: IntentRepresentation,
        answer: IntentRepresentation,
    ) -> FidelityScore:
        return FidelityScore.measured(0.95)


@pytest.mark.asyncio
async def test_full_run_attaches_all_intent_fidelity_surfaces() -> None:
    """One run exercises: intent capture, fidelity score on result, threshold
    ladder dispatching above_warn (no action change), and configured
    thresholds round-tripping through the config."""
    config = GuardConfig(
        observability=ObservabilityConfig(
            fidelity_thresholds=FidelityThresholds(
                warn=0.7,
                clarify=0.5,
                refuse=0.3,
            ),
        ),
    )
    pipeline = GuardPipeline(
        config=config,
        inspectors=[],
        intent_encoder=_StubEncoder(),
        fidelity_scorer=_MeasuringScorer(),
    )

    result = await pipeline.pre_process(GuardInput(text="benign question"))

    # Fidelity score attached.
    assert result.fidelity_score is not None
    assert result.fidelity_score.sentinel == "measured"
    assert result.fidelity_score.value == 0.95
    # Above_warn band → no fidelity-driven action.
    assert result.fidelity_warning is False
    assert result.clarification is None
    assert result.refusal is None
    assert result.action == "pass"


@pytest.mark.asyncio
async def test_default_pipeline_has_sentinel_score_and_no_action_change() -> None:
    """Null defaults: pipeline runs, sentinel attached, no action change."""
    pipeline = GuardPipeline(inspectors=[])
    result = await pipeline.pre_process(GuardInput(text="hello"))
    assert result.fidelity_score is not None
    assert result.fidelity_score.sentinel == "not_measured"
    assert result.fidelity_warning is False
    assert result.action == "pass"
