"""Deception types — score and per-conversation accumulator.

``DeceptionScore`` follows the same shape as ``FidelityScore`` (frozen
dataclass with ``value: float | None`` + ``sentinel`` discriminator)
but the direction is INVERTED: higher = more deception (worse), the
opposite of higher = more fidelity (better). The threshold ladder uses
the sibling ``DeceptionThresholds`` config with ``refuse > clarify >
warn`` ordering — the inverse of ``FidelityThresholds``.

``ConversationState`` is a per-conversation accumulator. It contains
zero raw turn text — counters and stable identifiers only. The state
is reconstructable from a sequence of past turns by replaying through
the inspector; the integration owns the lifecycle and threads it
forward across calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

DeceptionSentinel = Literal["measured", "not_measured"]


@dataclass(frozen=True)
class DeceptionScore:
    """A deception score in ``[0.0, 1.0]`` or the ``not_measured`` sentinel.

    **Direction**: higher = MORE deception (worse). This is the
    INVERSE of :class:`FidelityScore`, where higher = more fidelity
    (better). The threshold ladder uses :class:`DeceptionThresholds`
    with ``refuse > clarify > warn`` ordering.

    Validation rules:

    - ``sentinel == "measured"`` requires ``value`` in ``[0.0, 1.0]``.
    - ``sentinel == "not_measured"`` requires ``value is None``.

    Constructed via :meth:`measured` and :meth:`not_measured` rather
    than direct field assignment so the discriminator and value stay
    in sync.
    """

    value: float | None
    sentinel: DeceptionSentinel

    def __post_init__(self) -> None:
        if self.sentinel == "measured":
            if self.value is None:
                raise ValueError("DeceptionScore(sentinel='measured') requires a value")
            if not (0.0 <= self.value <= 1.0):
                raise ValueError(f"DeceptionScore.value must be in [0.0, 1.0]; got {self.value}")
        else:
            if self.value is not None:
                raise ValueError("DeceptionScore(sentinel='not_measured') must have value=None")

    @classmethod
    def measured(cls, value: float) -> DeceptionScore:
        return cls(value=value, sentinel="measured")

    @classmethod
    def not_measured(cls) -> DeceptionScore:
        return cls(value=None, sentinel="not_measured")


NOT_MEASURED: Final[DeceptionScore] = DeceptionScore(
    value=None,
    sentinel="not_measured",
)


@dataclass(frozen=True)
class ConversationState:
    """Per-conversation accumulator. Contains zero raw turn text.

    The integration's responsibility: construct an initial state with
    a stable ``conversation_id`` for each new conversation, thread it
    through ``GuardContext.conversation_state`` on each turn, and read
    the updated state back from ``GuardResult.conversation_state``
    (the top-level field, NOT ``result.context``).
    """

    conversation_id: str
    turn_count: int
    role_play_markers: int
    escalation_signals: int
    state_version: int = 1

    def __post_init__(self) -> None:
        if not self.conversation_id:
            raise ValueError("ConversationState.conversation_id must be non-empty")
        if self.turn_count < 1:
            raise ValueError(f"ConversationState.turn_count must be >= 1; got {self.turn_count}")
        if self.role_play_markers < 0:
            raise ValueError(
                f"ConversationState.role_play_markers must be >= 0; got {self.role_play_markers}"
            )
        if self.escalation_signals < 0:
            raise ValueError(
                f"ConversationState.escalation_signals must be >= 0; got {self.escalation_signals}"
            )


__all__ = [
    "DeceptionSentinel",
    "DeceptionScore",
    "NOT_MEASURED",
    "ConversationState",
]
