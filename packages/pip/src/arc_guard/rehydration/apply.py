"""``apply_rehydration`` — implements accept / reject / partial paths.

The verifier produces a ``RehydrationVerdict``; this helper takes the
verdict + the entity map + the placeholder-bearing text and returns the
final text. Emits ``guard.rehydration.applied`` (info) when at least
one placeholder was rehydrated and ``guard.rehydration.rejected``
(warn) when the verdict was reject or partial.

The helper does not consult the verifier itself; pipeline code calls
``verifier.verify(...)`` first, then passes the verdict here. This
keeps verifier choice (null vs. semantic) orthogonal to the apply
mechanics.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from arc_guard_core.observability import Logger, MetricSink
from arc_guard_core.protocols.rehydration_verifier import RehydrationVerdict

GUARD_REHYDRATION_APPLIED_EVENT: Final[str] = "guard.rehydration.applied"
GUARD_REHYDRATION_REJECTED_EVENT: Final[str] = "guard.rehydration.rejected"
REHYDRATION_VERDICT_COUNTER: Final[str] = "arc_guardrails.rehydration.verdict"


def apply_rehydration(
    text: str,
    verdict: RehydrationVerdict,
    entity_map: Mapping[str, str],
    *,
    correlation_id: str,
    decision_id: str,
    logger: Logger,
    metric_sink: MetricSink,
) -> str:
    """Apply ``verdict`` to ``text`` and emit observability.

    Returns the (possibly transformed) text. The verdict counter
    increments with attributes ``decision`` and ``reason``; the
    applied / rejected event carries the placeholder count or the
    rejection reason as documented.
    """
    placeholders_total = len(entity_map)
    placeholders_accepted = 0

    if verdict.decision == "accept":
        out = _substitute(text, entity_map, accept=lambda _name: True)
        placeholders_accepted = placeholders_total
        _emit_applied(
            placeholders_total=placeholders_total,
            placeholders_accepted=placeholders_accepted,
            correlation_id=correlation_id,
            decision_id=decision_id,
            logger=logger,
        )
    elif verdict.decision == "reject":
        out = text
        _emit_rejected(
            reason=verdict.reason,
            placeholders_total=placeholders_total,
            placeholders_accepted=0,
            correlation_id=correlation_id,
            decision_id=decision_id,
            logger=logger,
        )
    else:  # partial
        accepts = dict(verdict.per_placeholder)
        out = _substitute(
            text, entity_map, accept=lambda name: accepts.get(name, False),
        )
        placeholders_accepted = sum(1 for v in accepts.values() if v)
        # Partial counts as both applied AND rejected — the documented
        # semantics: the applied event signals at-least-one rehydration,
        # the rejected event signals at-least-one rejection.
        if placeholders_accepted > 0:
            _emit_applied(
                placeholders_total=placeholders_total,
                placeholders_accepted=placeholders_accepted,
                correlation_id=correlation_id,
                decision_id=decision_id,
                logger=logger,
            )
        if placeholders_accepted < placeholders_total:
            _emit_rejected(
                reason=verdict.reason,
                placeholders_total=placeholders_total,
                placeholders_accepted=placeholders_accepted,
                correlation_id=correlation_id,
                decision_id=decision_id,
                logger=logger,
            )

    metric_sink.counter(
        REHYDRATION_VERDICT_COUNTER,
        attributes={
            "decision": verdict.decision,
            "reason": verdict.reason,
        },
    )
    return out


def _substitute(
    text: str,
    entity_map: Mapping[str, str],
    *,
    accept: Any,
) -> str:
    """Replace placeholder names with entity values where ``accept(name)`` is True."""
    out = text
    for placeholder, original in entity_map.items():
        if accept(placeholder):
            out = out.replace(placeholder, original)
    return out


def _emit_applied(
    *,
    placeholders_total: int,
    placeholders_accepted: int,
    correlation_id: str,
    decision_id: str,
    logger: Logger,
) -> None:
    logger.event(
        GUARD_REHYDRATION_APPLIED_EVENT,
        level="info",
        correlation_id=correlation_id,
        decision_id=decision_id,
        placeholders_total=placeholders_total,
        placeholders_accepted=placeholders_accepted,
    )


def _emit_rejected(
    *,
    reason: str,
    placeholders_total: int,
    placeholders_accepted: int,
    correlation_id: str,
    decision_id: str,
    logger: Logger,
) -> None:
    logger.event(
        GUARD_REHYDRATION_REJECTED_EVENT,
        level="warn",
        correlation_id=correlation_id,
        decision_id=decision_id,
        reason=reason,
        placeholders_total=placeholders_total,
        placeholders_accepted=placeholders_accepted,
    )


__all__ = [
    "apply_rehydration",
    "GUARD_REHYDRATION_APPLIED_EVENT",
    "GUARD_REHYDRATION_REJECTED_EVENT",
    "REHYDRATION_VERDICT_COUNTER",
]
