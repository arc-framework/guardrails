"""Non-default deception thresholds drive the ladder per the configured boundaries."""

from __future__ import annotations

import pytest
from arc_guard_core.deception import ConversationState, DeceptionScore
from arc_guard_core.observability_config import (
    DeceptionThresholds,
    ObservabilityConfig,
)
from arc_guard_core.types import GuardContext, GuardInput

from arc_guard.config_env import GuardConfig
from arc_guard.pipeline import GuardPipeline


class _FixedScoreInspector:
    """Returns a fixed measured score regardless of input."""

    def __init__(self, *, value: float) -> None:
        self._value = value

    def inspect_turn(
        self,
        text: str,
        *,
        prior_state: ConversationState | None,
    ) -> tuple[DeceptionScore, ConversationState]:
        from arc_guard.deception.state import fresh_state, update_state

        if prior_state is None:
            return (
                DeceptionScore.measured(self._value),
                fresh_state("test-conv-1"),
            )
        return (
            DeceptionScore.measured(self._value),
            update_state(prior_state, text),
        )


def _no_op_jailbreak() -> object:
    """Pin scope to deception ladder by disabling jailbreak detector."""

    class _NoOp:
        @property
        def detector_id(self) -> str:
            return "noop:1"

        def detect(self, text, *, conversation_state=None):
            return ()

    return _NoOp()


@pytest.mark.asyncio
async def test_aggressive_thresholds_promote_low_score_to_refuse() -> None:
    """With ``refuse=0.4``, a score of 0.5 lands in the refuse band."""
    config = GuardConfig(
        observability=ObservabilityConfig(
            deception_thresholds=DeceptionThresholds(
                refuse=0.4, clarify=0.2, warn=0.1,
            ),
        ),
    )
    pipeline = GuardPipeline(
        config=config,
        inspectors=[],
        jailbreak_detector=_no_op_jailbreak(),
        conversation_turn_inspector=_FixedScoreInspector(value=0.5),
    )
    # Need a prior_state to get a measured score (not_measured on first turn).
    from arc_guard.deception.state import fresh_state

    state = fresh_state("test-conv-1")
    result = await pipeline.pre_process(
        GuardInput(text="anything", context=GuardContext(conversation_state=state))
    )
    assert result.action == "block"
    assert result.refusal is not None
    assert result.refusal.code == "deception_drift"


@pytest.mark.asyncio
async def test_conservative_thresholds_keep_moderate_score_passing() -> None:
    """With ``refuse=0.9``, a score of 0.4 doesn't trip any band."""
    config = GuardConfig(
        observability=ObservabilityConfig(
            deception_thresholds=DeceptionThresholds(
                refuse=0.9, clarify=0.7, warn=0.5,
            ),
        ),
    )
    pipeline = GuardPipeline(
        config=config,
        inspectors=[],
        jailbreak_detector=_no_op_jailbreak(),
        conversation_turn_inspector=_FixedScoreInspector(value=0.4),
    )
    from arc_guard.deception.state import fresh_state

    state = fresh_state("test-conv-1")
    result = await pipeline.pre_process(
        GuardInput(text="anything", context=GuardContext(conversation_state=state))
    )
    assert result.action == "pass"
    assert result.refusal is None
    assert result.clarification is None
