"""FidelityScorer Protocol — scores semantic alignment between intents.

Implementations take two ``IntentRepresentation`` opaque values from a
compatible encoder and return a ``FidelityScore``. The score's value is
in ``[0.0, 1.0]`` when measured (higher = more aligned); the
``not_measured`` sentinel signals the scorer could not produce a
meaningful number (e.g. one of the inputs is the null encoder's marker).

Failure mode: implementations MUST NOT raise outward. Internal failures
are wrapped in ``FidelityScorerError`` whose foundation
``__failure_mode__`` is ``open`` — scorer hiccups log + count but do not
refuse the run; the score defaults to the sentinel.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from arc_guard_core.fidelity import FidelityScore
from arc_guard_core.protocols.intent_encoder import (
    IntentEncoder,
    IntentRepresentation,
)


@runtime_checkable
class FidelityScorer(Protocol):
    """Score the semantic alignment between two intent representations.

    Concurrency: thread-safe.
    Failure mode: implementations MUST NOT raise outward; internal
    failures bubble via ``FidelityScorerError`` (foundation
    ``__failure_mode__='open'``) so scoring hiccups log + count without
    refusing the run; the score defaults to the sentinel.
    """

    def compatible_with(self, encoder: IntentEncoder) -> bool:
        """Return True when this scorer can handle ``encoder``'s representations.

        Called once at pipeline-construction time. A False return raises
        ``ConfigCrossFieldError`` at construction so the run never starts
        with a misconfigured pair. The check MUST be cheap (string
        comparison, version match); MUST NOT involve I/O.
        """

    def score(
        self,
        intent: IntentRepresentation,
        answer: IntentRepresentation,
    ) -> FidelityScore:
        """Return a ``FidelityScore`` for the (intent, answer) pair."""


__all__ = ["FidelityScorer"]
