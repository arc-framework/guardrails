"""IntentEncoder Protocol — encodes prompts and answers into intent representations.

Implementations turn a UTF-8 string into an opaque ``IntentRepresentation``
that the paired ``FidelityScorer`` knows how to compare. The
representation type is encoder-private; callers MUST NOT inspect it.

Failure mode: implementations MUST NOT raise outward. Internal failures
(model load error, timeout, inference error) are wrapped in
``IntentEncoderError`` whose foundation ``__failure_mode__`` is
``closed-conservative`` so the pipeline degrades to the
``FidelityScore.NOT_MEASURED`` sentinel instead of refusing the run.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

# ``IntentRepresentation`` is encoder-private. Aliasing to ``Any`` keeps
# the Protocol surface stable across encoder shapes (vector embeddings,
# structural fingerprints, retrieval-grounded fact sets) per the R1
# decision in research.md.
IntentRepresentation = Any


@runtime_checkable
class IntentEncoder(Protocol):
    """Encode text into an opaque intent representation.

    Concurrency: thread-safe — multiple concurrent ``encode`` calls on
    the same instance produce correct, independent results.
    Failure mode: implementations MUST NOT raise outward; internal
    failures bubble via ``IntentEncoderError`` (foundation
    ``__failure_mode__='closed-conservative'``) so the pipeline degrades
    to ``FidelityScore.NOT_MEASURED`` instead of refusing the run.
    """

    @property
    def encoder_id(self) -> str:
        """Stable ``<name>:<version>`` marker.

        Read by ``FidelityScorer.compatible_with`` at construction time;
        recorded verbatim on ``IntentLock.encoder_id`` for audit. The id
        MUST NOT include host-specific data.
        """

    def encode(self, text: str) -> IntentRepresentation:
        """Return an opaque representation suitable for fidelity comparison."""


__all__ = [
    "IntentEncoder",
    "IntentRepresentation",
]
