"""``NullIntentEncoder`` + the ``capture_intent`` stage-orchestration helper.

The null encoder returns a documented sentinel marker that the matching
``NullFidelityScorer`` recognizes; the pair preserves the offline-capable
rule (no concrete extra installed → fidelity score is the
``NOT_MEASURED`` sentinel).

``capture_intent`` runs an arbitrary ``IntentEncoder`` via the asyncio
offload helper (so heavy embedding models do not block the event loop),
emits the documented ``guard.intent.captured`` event, and returns the
encoded representation to the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from arc_guard_core.observability import Logger, MetricSink
from arc_guard_core.protocols.intent_encoder import (
    IntentEncoder,
    IntentRepresentation,
)

from arc_guard.concurrency.offload import run_off_loop


@dataclass(frozen=True)
class _NullIntentMarker:
    """Sentinel returned by ``NullIntentEncoder.encode``.

    Frozen so it is hashable + safe to share across concurrent runs.
    The matching ``NullFidelityScorer`` checks ``isinstance`` against
    this type to recognize the null pair without importing the encoder.
    """

    encoder_id: str = "null:1"


NULL_INTENT_REPRESENTATION: Final[_NullIntentMarker] = _NullIntentMarker()


class NullIntentEncoder:
    """Default offline-capable encoder: returns a stable sentinel marker.

    ``encoder_id`` is ``"null:1"``; ``encode(text)`` returns the
    module-level ``NULL_INTENT_REPRESENTATION`` singleton regardless
    of input. The matching ``NullFidelityScorer`` returns the
    ``NOT_MEASURED`` sentinel for any input pair containing this marker.
    """

    @property
    def encoder_id(self) -> str:
        return "null:1"

    def encode(self, text: str) -> IntentRepresentation:
        return NULL_INTENT_REPRESENTATION


GUARD_INTENT_CAPTURED_EVENT: Final[str] = "guard.intent.captured"


async def capture_intent(
    text: str,
    *,
    encoder: IntentEncoder,
    correlation_id: str,
    decision_id: str,
    logger: Logger,
    metric_sink: MetricSink,
) -> IntentRepresentation:
    """Encode ``text`` via ``encoder`` and emit ``guard.intent.captured``.

    The encode call goes through the asyncio offload helper so heavy
    embedding inference does not block the event loop. The event
    carries ``encoder_id`` and ``intent_size_bytes`` (size of the
    canonical-form text, NOT the raw text) for operator dashboarding.
    """
    representation = await run_off_loop(
        encoder.encode,
        text,
        stage="defend",
        metric_sink=metric_sink,
    )
    intent_size_bytes = len(text.encode("utf-8"))
    fields: dict[str, Any] = {
        "correlation_id": correlation_id,
        "decision_id": decision_id,
        "encoder_id": encoder.encoder_id,
        "intent_size_bytes": intent_size_bytes,
    }
    logger.event(GUARD_INTENT_CAPTURED_EVENT, level="info", **fields)
    return representation


__all__ = [
    "NullIntentEncoder",
    "NULL_INTENT_REPRESENTATION",
    "capture_intent",
    "GUARD_INTENT_CAPTURED_EVENT",
]
