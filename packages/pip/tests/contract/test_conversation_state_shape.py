"""``ConversationState`` schema + invariants."""

from __future__ import annotations

import dataclasses

import pytest
from arc_guard_core.deception import ConversationState


def test_valid_state_round_trips() -> None:
    state = ConversationState(
        conversation_id="conv-1",
        turn_count=1,
        role_play_markers=0,
        escalation_signals=0,
    )
    assert state.conversation_id == "conv-1"
    assert state.turn_count == 1
    assert state.state_version == 1


def test_empty_conversation_id_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        ConversationState(
            conversation_id="",
            turn_count=1,
            role_play_markers=0,
            escalation_signals=0,
        )


def test_zero_turn_count_rejected() -> None:
    with pytest.raises(ValueError, match=">= 1"):
        ConversationState(
            conversation_id="c1",
            turn_count=0,
            role_play_markers=0,
            escalation_signals=0,
        )


def test_negative_turn_count_rejected() -> None:
    with pytest.raises(ValueError, match=">= 1"):
        ConversationState(
            conversation_id="c1",
            turn_count=-1,
            role_play_markers=0,
            escalation_signals=0,
        )


def test_negative_role_play_markers_rejected() -> None:
    with pytest.raises(ValueError, match="role_play_markers"):
        ConversationState(
            conversation_id="c1",
            turn_count=1,
            role_play_markers=-1,
            escalation_signals=0,
        )


def test_negative_escalation_signals_rejected() -> None:
    with pytest.raises(ValueError, match="escalation_signals"):
        ConversationState(
            conversation_id="c1",
            turn_count=1,
            role_play_markers=0,
            escalation_signals=-1,
        )


def test_state_version_default_is_1() -> None:
    state = ConversationState(
        conversation_id="c1",
        turn_count=1,
        role_play_markers=0,
        escalation_signals=0,
    )
    assert state.state_version == 1


def test_frozen_rejects_mutation() -> None:
    state = ConversationState(
        conversation_id="c1",
        turn_count=1,
        role_play_markers=0,
        escalation_signals=0,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.turn_count = 5  # type: ignore[misc]
