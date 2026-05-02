"""``StatefulConversationInspector`` first-turn sentinel behavior."""

from __future__ import annotations

from arc_guard.deception.inspector import StatefulConversationInspector


def test_first_turn_returns_sentinel_score() -> None:
    inspector = StatefulConversationInspector()
    score, state = inspector.inspect_turn(
        "anything goes here", prior_state=None,
    )
    assert score.sentinel == "not_measured"
    assert score.value is None


def test_first_turn_returns_fresh_state_with_turn_count_1() -> None:
    inspector = StatefulConversationInspector()
    _, state = inspector.inspect_turn("hello", prior_state=None)
    assert state.turn_count == 1
    assert state.role_play_markers == 0
    assert state.escalation_signals == 0
    assert state.conversation_id  # non-empty


def test_subsequent_turn_returns_measured_score() -> None:
    inspector = StatefulConversationInspector()
    _, s1 = inspector.inspect_turn("turn 1", prior_state=None)
    score, s2 = inspector.inspect_turn("turn 2", prior_state=s1)
    assert score.sentinel == "measured"
    assert score.value is not None
    assert 0.0 <= score.value <= 1.0
    assert s2.turn_count == 2


def test_default_conversation_id_seed_is_used_for_fresh_state() -> None:
    inspector = StatefulConversationInspector(default_conversation_id="seed-id")
    _, state = inspector.inspect_turn("anything", prior_state=None)
    assert state.conversation_id == "seed-id"
