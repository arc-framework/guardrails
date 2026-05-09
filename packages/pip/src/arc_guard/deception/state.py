"""``ConversationState`` reducer — fresh / update.

Pure-arithmetic counter accumulator. The reducer matches the current
turn's text against role-play patterns and escalation patterns and
increments the corresponding counters. Never stores raw turn text.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable

from arc_guard_core.deception import ConversationState

_ROLE_PLAY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\byou\s+are\s+(?:now\s+)?(?:DAN|an\s+unrestricted|jailbroken|evil|uncensored)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bact\s+as\s+(?:if\s+you\s+(?:were|are)\s+)?(?:an?\s+)?(?:unrestricted|jailbroken|evil|uncensored|character|persona)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:from\s+now\s+on|imagine\s+that)\s+you\s+are\b", re.IGNORECASE),
    re.compile(r"\bpretend\s+(?:to\s+be|you\s+(?:are|were))\b", re.IGNORECASE),
    re.compile(r"\brole[\s-]?play\s+as\b", re.IGNORECASE),
    re.compile(r"\bplay\s+the\s+(?:part|role)\s+of\b", re.IGNORECASE),
)


_ESCALATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bas\s+we\s+(?:already\s+)?(?:agreed|discussed|established)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:we|you)\s+(?:already\s+)?(?:agreed|discussed|established)\s+(?:that|earlier)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bas\s+i\s+mentioned\s+(?:before|earlier)\b", re.IGNORECASE),
    re.compile(r"\bnow\s+that\s+(?:we|you)\s+(?:have|are)\b", re.IGNORECASE),
    re.compile(r"\bpush\s+the\s+boundaries\b", re.IGNORECASE),
    re.compile(r"\bbe\s+more\s+direct\b", re.IGNORECASE),
    re.compile(r"\bjust\s+(?:between\s+us|hypothetically)\b", re.IGNORECASE),
    re.compile(r"\bwe\s+both\s+know\b", re.IGNORECASE),
    re.compile(r"\bfor\s+educational\s+purposes\s+only\b", re.IGNORECASE),
    re.compile(r"\bthis\s+is\s+just\s+a\s+test\b", re.IGNORECASE),
)


def _count_matches(
    text: str,
    patterns: Iterable[re.Pattern[str]],
) -> int:
    """Count distinct patterns that match (not total match count).

    Multiple matches of the same pattern collapse into one increment so
    a pattern that fires twice in a single turn doesn't double-count
    the escalation signal.
    """
    return sum(1 for pattern in patterns if pattern.search(text))


def fresh_state(conversation_id: str | None = None) -> ConversationState:
    """Initial state for a new conversation.

    When ``conversation_id`` is ``None``, a fresh UUID4 is synthesized.
    Operators who care about cross-turn correlation in observability
    pass an explicit id.
    """
    return ConversationState(
        conversation_id=conversation_id or uuid.uuid4().hex,
        turn_count=1,
        role_play_markers=0,
        escalation_signals=0,
    )


def update_state(
    prior_state: ConversationState,
    current_turn_text: str,
) -> ConversationState:
    """Return a new ``ConversationState`` after observing ``current_turn_text``.

    Increments ``turn_count`` by 1, plus the role-play / escalation
    counters by the number of distinct matching patterns in this turn.
    The returned state contains zero raw turn text.
    """
    role_play_delta = _count_matches(current_turn_text, _ROLE_PLAY_PATTERNS)
    escalation_delta = _count_matches(current_turn_text, _ESCALATION_PATTERNS)
    return ConversationState(
        conversation_id=prior_state.conversation_id,
        turn_count=prior_state.turn_count + 1,
        role_play_markers=prior_state.role_play_markers + role_play_delta,
        escalation_signals=prior_state.escalation_signals + escalation_delta,
        state_version=prior_state.state_version,
    )


__all__ = ["fresh_state", "update_state"]
