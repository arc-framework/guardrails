"""Deception detection sub-package: stateful inspector + ladder helpers."""

from __future__ import annotations

from arc_guard.deception.inspector import (
    GUARD_DECEPTION_SCORED_EVENT,
    StatefulConversationInspector,
)
from arc_guard.deception.ladder import apply_deception_ladder
from arc_guard.deception.state import fresh_state, update_state

__all__ = [
    "StatefulConversationInspector",
    "apply_deception_ladder",
    "fresh_state",
    "update_state",
    "GUARD_DECEPTION_SCORED_EVENT",
]
