"""``StatefulConversationInspector`` — accumulates state across turns.

Cheap-heuristic deception detector. Computes the deception score as a
function of the role-play and escalation counters normalized by the
turn count. Higher score = more deception (INVERSE direction relative
to ``FidelityScore``).

Failure mode: failures wrapped in ``ConversationTurnInspectorError``;
posture ``closed-conservative`` — the pipeline emits
``DeceptionScore.NOT_MEASURED`` rather than refusing the run.
"""

from __future__ import annotations

from typing import Final

from arc_guard_core.deception import ConversationState, DeceptionScore
from arc_guard_core.exceptions import ConversationTurnInspectorError

from arc_guard.deception.state import fresh_state, update_state

GUARD_DECEPTION_SCORED_EVENT: Final[str] = "guard.deception.scored"


class StatefulConversationInspector:
    """Default offline-capable inspector using cheap counter heuristics.

    Concurrency: thread-safe (state is passed in, no instance state).
    Failure mode: failures wrapped in ``ConversationTurnInspectorError``;
    posture ``closed-conservative``.
    """

    def __init__(self, *, default_conversation_id: str | None = None) -> None:
        # Operators may set a default conversation_id seed; otherwise
        # the inspector synthesizes a UUID4 for fresh conversations.
        self._default_conversation_id = default_conversation_id

    def inspect_turn(
        self,
        text: str,
        *,
        prior_state: ConversationState | None,
    ) -> tuple[DeceptionScore, ConversationState]:
        try:
            if prior_state is None:
                # First turn / single-turn mode — return sentinel + a
                # fresh state with turn_count=1. The threshold ladder
                # treats the sentinel as a no-op.
                return (
                    DeceptionScore.not_measured(),
                    fresh_state(self._default_conversation_id),
                )
            updated = update_state(prior_state, text)
            value = self._score(updated)
            return (DeceptionScore.measured(value), updated)
        except ConversationTurnInspectorError:
            raise
        except Exception as exc:  # pragma: no cover — defensive
            raise ConversationTurnInspectorError(
                f"inspector raised: {exc}",
                code="conversation_turn_inspector.inference_failed",
                cause=exc,
            ) from exc

    @staticmethod
    def _score(state: ConversationState) -> float:
        """Compute deception score from accumulated counters.

        Per-turn ratio of role-play + escalation signals over turn
        count, clamped to ``[0.0, 1.0]``. The denominator uses
        ``max(turn_count, 1)`` for safety; turn_count is always >= 1
        on a valid state.
        """
        denom = max(state.turn_count, 1)
        signals = state.role_play_markers + state.escalation_signals
        raw = signals / denom
        return min(1.0, max(0.0, raw))


__all__ = ["StatefulConversationInspector", "GUARD_DECEPTION_SCORED_EVENT"]
