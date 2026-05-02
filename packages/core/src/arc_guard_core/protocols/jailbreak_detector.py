"""JailbreakDetector Protocol — produces typed jailbreak signals per input.

Implementations detect role-play coercion, hypothetical framing,
gradual policy erosion, indirect prompt injection, and direct override
patterns. Each detected pattern becomes a ``JailbreakSignal`` with a
category, confidence, and a placeholder evidence reference.

Failure mode: implementations MUST NOT raise outward. Internal
failures (model load, timeout, inference) are wrapped in
``JailbreakDetectorError`` whose foundation ``__failure_mode__`` is
``closed-conservative`` so a detector hiccup falls through to no
signal rather than producing a false-positive refusal.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from arc_guard_core.deception import ConversationState
from arc_guard_core.jailbreak import JailbreakSignal


@runtime_checkable
class JailbreakDetector(Protocol):
    """Detect jailbreak attempts and emit per-category signals.

    Concurrency: thread-safe — multiple concurrent ``detect`` calls
    on the same instance produce correct, independent results.
    Failure mode: implementations MUST NOT raise outward; internal
    failures bubble via ``JailbreakDetectorError`` (foundation
    ``__failure_mode__='closed-conservative'``) so the pipeline
    produces no signal rather than a false-positive refusal.
    """

    @property
    def detector_id(self) -> str:
        """Stable ``<name>:<version>`` marker; recorded on every signal."""

    def detect(
        self,
        text: str,
        *,
        conversation_state: ConversationState | None = None,
    ) -> tuple[JailbreakSignal, ...]:
        """Return zero or more signals for the input text.

        Multi-turn detectors MAY use ``conversation_state`` to inform
        per-turn detection (e.g., role-play markers across turns);
        single-turn detectors ignore it.
        """


__all__ = ["JailbreakDetector"]
