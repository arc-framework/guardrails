"""``NullFidelityScorer`` + the ``score_fidelity`` stage-orchestration helper.

The null scorer recognizes the null encoder's sentinel marker by type
(no import of the encoder needed at the public surface), and returns
the ``NOT_MEASURED`` sentinel for any input pair. The matching encoder
is ``NullIntentEncoder`` (encoder_id ``"null:1"``). Custom encoders
that follow the ``"null:..."`` id prefix are also accepted for
compatibility — operators with their own no-op encoder do not need to
patch the scorer.

``score_fidelity`` runs an arbitrary ``FidelityScorer`` via the asyncio
offload helper, emits the documented ``guard.fidelity.scored`` event,
and increments the ``arc_guardrails.fidelity.score`` counter.
"""

from __future__ import annotations

import time
from typing import Any, Final

from arc_guard_core.fidelity import NOT_MEASURED, FidelityScore
from arc_guard_core.observability import Logger, MetricSink
from arc_guard_core.observability_config import FidelityThresholds
from arc_guard_core.protocols.fidelity_scorer import FidelityScorer
from arc_guard_core.protocols.intent_encoder import (
    IntentEncoder,
    IntentRepresentation,
)

from arc_guard.concurrency.offload import run_off_loop

GUARD_FIDELITY_SCORED_EVENT: Final[str] = "guard.fidelity.scored"
FIDELITY_SCORE_COUNTER: Final[str] = "arc_guardrails.fidelity.score"
FIDELITY_DURATION_HISTOGRAM: Final[str] = "arc_guardrails.fidelity.duration"


class NullFidelityScorer:
    """Default offline-capable scorer: returns the ``NOT_MEASURED`` sentinel.

    Compatible with any encoder whose ``encoder_id`` starts with
    ``"null:"``. Returns the ``NOT_MEASURED`` sentinel for any input
    pair, including pairs that contain the null encoder's
    ``_NullIntentMarker`` singleton — the threshold ladder treats the
    sentinel as a no-op, so the action is unaffected.
    """

    def compatible_with(self, encoder: IntentEncoder) -> bool:
        return encoder.encoder_id.startswith("null:")

    def score(
        self,
        intent: IntentRepresentation,
        answer: IntentRepresentation,
    ) -> FidelityScore:
        # The null scorer never produces a measured value; it returns
        # the sentinel for any input. Even when a non-null
        # representation is paired (operator misconfiguration), the
        # sentinel keeps the threshold ladder a no-op rather than
        # fabricating a meaningless score.
        del intent, answer
        return NOT_MEASURED


def _band(score: FidelityScore, thresholds: FidelityThresholds) -> str:
    if score.sentinel != "measured" or score.value is None:
        return "not_measured"
    if score.value >= thresholds.warn:
        return "above_warn"
    if score.value >= thresholds.clarify:
        return "warn"
    if score.value >= thresholds.refuse:
        return "clarify"
    return "refuse"


async def score_fidelity(
    intent: IntentRepresentation,
    answer: IntentRepresentation,
    *,
    scorer: FidelityScorer,
    thresholds: FidelityThresholds,
    correlation_id: str,
    decision_id: str,
    logger: Logger,
    metric_sink: MetricSink,
) -> FidelityScore:
    """Score ``(intent, answer)`` via ``scorer`` and emit observability.

    The score call goes through the asyncio offload helper. The
    ``guard.fidelity.scored`` event carries the value, sentinel, and
    band; the score counter and duration histogram are updated with
    matching attributes.
    """
    started_ns = time.monotonic_ns()
    score = await run_off_loop(
        scorer.score,
        intent,
        answer,
        stage="verify",
        metric_sink=metric_sink,
    )
    duration_ms = (time.monotonic_ns() - started_ns) / 1_000_000.0
    band = _band(score, thresholds)
    fields: dict[str, Any] = {
        "correlation_id": correlation_id,
        "decision_id": decision_id,
        "score_value": score.value,
        "score_sentinel": score.sentinel,
        "band": band,
    }
    logger.event(GUARD_FIDELITY_SCORED_EVENT, level="info", **fields)
    metric_sink.counter(
        FIDELITY_SCORE_COUNTER,
        attributes={"band": band, "sentinel": score.sentinel},
    )
    metric_sink.histogram(
        FIDELITY_DURATION_HISTOGRAM,
        duration_ms,
        attributes={"band": band, "sentinel": score.sentinel},
    )
    return score


# Re-exported so other modules (the threshold ladder, observability
# tests) can ask for the band of a given score without re-implementing
# the logic. Underscore is intentionally absent for the public name.
band_for_score = _band


__all__ = [
    "NullFidelityScorer",
    "score_fidelity",
    "band_for_score",
    "GUARD_FIDELITY_SCORED_EVENT",
    "FIDELITY_SCORE_COUNTER",
    "FIDELITY_DURATION_HISTOGRAM",
]
