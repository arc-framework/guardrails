"""ConversationTurnInspector Protocol — produces per-turn deception scores.

Implementations accumulate role-play markers and escalation signals
across the turns of a conversation. The inspector reads the prior
``ConversationState`` (or ``None`` for the first turn) and the current
turn's text, returns a ``DeceptionScore`` and an updated
``ConversationState``. The integration threads the state forward
across calls.

Failure mode: implementations MUST NOT raise outward. Internal
failures are wrapped in ``ConversationTurnInspectorError`` whose
foundation ``__failure_mode__`` is ``closed-conservative`` — the
pipeline emits ``DeceptionScore.NOT_MEASURED`` rather than refusing
the run.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from arc_guard_core.deception import ConversationState, DeceptionScore


@runtime_checkable
class ConversationTurnInspector(Protocol):
    """Detect multi-turn deception by accumulating state across turns.

    Concurrency: thread-safe.
    Failure mode: implementations MUST NOT raise outward; internal
    failures bubble via ``ConversationTurnInspectorError`` (foundation
    ``__failure_mode__='closed-conservative'``) so the pipeline emits
    ``DeceptionScore.NOT_MEASURED`` instead of refusing.
    """

    def inspect_turn(
        self,
        text: str,
        *,
        prior_state: ConversationState | None,
    ) -> tuple[DeceptionScore, ConversationState]:
        """Return ``(score, updated_state)`` for the current turn.

        ``prior_state=None`` is the first turn or single-turn mode;
        the inspector returns the documented sentinel score and an
        initial state with ``turn_count=1``.
        """


__all__ = ["ConversationTurnInspector"]
