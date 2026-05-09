"""Non-default jailbreak thresholds drive the ladder per the configured boundaries."""

from __future__ import annotations

import pytest
from arc_guard_core.deception import ConversationState
from arc_guard_core.jailbreak import JailbreakSignal
from arc_guard_core.observability_config import (
    JailbreakThresholds,
    ObservabilityConfig,
)
from arc_guard_core.types import GuardInput

from arc_guard.config_env import GuardConfig
from arc_guard.pipeline import GuardPipeline


class _FixedDetector:
    """Stub detector returning a single configurable signal."""

    def __init__(self, *, confidence: float) -> None:
        self._confidence = confidence

    @property
    def detector_id(self) -> str:
        return "fixed-stub:1"

    def detect(
        self, text: str, *, conversation_state: ConversationState | None = None,
    ) -> tuple[JailbreakSignal, ...]:
        del text, conversation_state
        return (
            JailbreakSignal(
                category="direct_override",
                confidence=self._confidence,
                evidence_reference="STUB",
                detector_id=self.detector_id,
            ),
        )


@pytest.mark.asyncio
async def test_aggressive_thresholds_promote_borderline_to_refuse() -> None:
    """With ``refuse=0.5``, a confidence of 0.6 lands in the refuse band."""
    config = GuardConfig(
        observability=ObservabilityConfig(
            jailbreak_thresholds=JailbreakThresholds(
                refuse=0.5, clarify=0.3, warn=0.15,
            ),
        ),
    )
    pipeline = GuardPipeline(
        config=config,
        inspectors=[],
        jailbreak_detector=_FixedDetector(confidence=0.6),
    )
    result = await pipeline.pre_process(GuardInput(text="hello"))
    assert result.action == "block"
    assert result.refusal is not None
    assert result.refusal.code == "jailbreak_strong"


@pytest.mark.asyncio
async def test_conservative_thresholds_keep_high_confidence_in_clarify() -> None:
    """With ``refuse=0.95``, a confidence of 0.85 lands in clarify band."""
    config = GuardConfig(
        observability=ObservabilityConfig(
            jailbreak_thresholds=JailbreakThresholds(
                refuse=0.95, clarify=0.7, warn=0.4,
            ),
        ),
    )
    pipeline = GuardPipeline(
        config=config,
        inspectors=[],
        jailbreak_detector=_FixedDetector(confidence=0.85),
    )
    result = await pipeline.pre_process(GuardInput(text="hello"))
    assert result.action != "block"
    assert result.clarification is not None


@pytest.mark.asyncio
async def test_default_thresholds_keep_low_confidence_below_ladder() -> None:
    """Default (refuse=0.8): confidence 0.3 doesn't trip any LADDER band.

    The legacy single-strategy path may still process the finding via
    ``RedactStrategy`` (action="redact"), but the jailbreak ladder
    itself MUST NOT have dispatched — no JAILBREAK_STRONG refusal and
    no ladder-driven clarification.
    """
    pipeline = GuardPipeline(
        inspectors=[],
        jailbreak_detector=_FixedDetector(confidence=0.3),
    )
    result = await pipeline.pre_process(GuardInput(text="hello"))
    # Ladder did not fire.
    if result.refusal is not None:
        assert result.refusal.code != "jailbreak_strong"
    assert result.action != "block"
