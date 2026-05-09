"""Structural-conformance tests for the ``ConversationTurnInspector`` Protocol."""

from __future__ import annotations

from arc_guard_core.deception import ConversationState, DeceptionScore
from arc_guard_core.protocols import ConversationTurnInspector


class _StubInspector:
    def inspect_turn(
        self,
        text: str,
        *,
        prior_state: ConversationState | None,
    ) -> tuple[DeceptionScore, ConversationState]:
        if prior_state is None:
            return (
                DeceptionScore.not_measured(),
                ConversationState(
                    conversation_id="stub-conv-1",
                    turn_count=1,
                    role_play_markers=0,
                    escalation_signals=0,
                ),
            )
        from dataclasses import replace

        next_state = replace(
            prior_state,
            turn_count=prior_state.turn_count + 1,
        )
        return (DeceptionScore.measured(0.3), next_state)


def test_conversation_turn_inspector_is_runtime_checkable() -> None:
    assert isinstance(_StubInspector(), ConversationTurnInspector)


def test_first_turn_returns_sentinel_and_fresh_state() -> None:
    inspector = _StubInspector()
    score, state = inspector.inspect_turn("hello", prior_state=None)
    assert score.sentinel == "not_measured"
    assert state.turn_count == 1
    assert state.role_play_markers == 0


def test_subsequent_turn_increments_turn_count() -> None:
    inspector = _StubInspector()
    _, s1 = inspector.inspect_turn("turn 1", prior_state=None)
    _, s2 = inspector.inspect_turn("turn 2", prior_state=s1)
    assert s2.turn_count == 2
    _, s3 = inspector.inspect_turn("turn 3", prior_state=s2)
    assert s3.turn_count == 3


def test_subsequent_turn_returns_measured_score() -> None:
    inspector = _StubInspector()
    _, s1 = inspector.inspect_turn("turn 1", prior_state=None)
    score, _ = inspector.inspect_turn("turn 2", prior_state=s1)
    assert score.sentinel == "measured"
    assert score.value is not None
    assert 0.0 <= score.value <= 1.0
