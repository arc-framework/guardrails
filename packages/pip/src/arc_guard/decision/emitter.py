"""DecisionRecord builder + emitter."""

from __future__ import annotations

import contextlib
import dataclasses

from arc_guard_core.decision import DecisionRecord, FindingSummary
from arc_guard_core.fidelity import FidelityScore
from arc_guard_core.intent_lock import IntentLock
from arc_guard_core.observability import Logger, MetricSink
from arc_guard_core.policy import RoutedOutcome
from arc_guard_core.types import GuardResult


class DecisionEmitter:
    """Builds typed DecisionRecord summaries and emits them through hooks."""

    def build(
        self,
        result: GuardResult,
        outcome: RoutedOutcome,
        latency_ms: float,
        *,
        intent_lock: IntentLock | None = None,
        fidelity_score: FidelityScore | None = None,
    ) -> DecisionRecord:
        finding_summaries = tuple(
            FindingSummary(
                entity_type=f.entity_type,
                start=f.start,
                end=f.end,
                length=f.end - f.start,
                risk_level=f.risk_level,
                inspector=f.inspector,
                score=f.score,
            )
            for f in result.findings
        )
        return DecisionRecord(
            correlation_id=getattr(result, "correlation_id", None),
            phase=result.phase,
            aggregate_action=str(outcome.aggregate_action),
            aggregate_band=outcome.aggregate_band,
            findings=finding_summaries,
            transforms=outcome.transforms,
            fired_rules=outcome.fired_rule_ids,
            refusal_code=(outcome.refusal.code if outcome.refusal else None),
            clarification_present=outcome.clarification is not None,
            latency_ms=latency_ms,
            intent_lock=intent_lock,
            fidelity_score=fidelity_score,
        )

    def emit(
        self,
        record: DecisionRecord,
        *,
        logger: Logger,
        metrics: MetricSink,
    ) -> None:
        # Constitution Principle V: emission MUST NOT raise back.
        with contextlib.suppress(Exception):
            logger.event(
                "guard.decision",
                level="info",
                **dataclasses.asdict(record),
            )
        with contextlib.suppress(Exception):
            metrics.counter(
                "guard.decisions",
                attributes={
                    "action": record.aggregate_action,
                    "risk_band": record.aggregate_band.value,
                },
            )
            metrics.histogram(
                "guard.findings_count",
                float(len(record.findings)),
            )


__all__ = ["DecisionEmitter"]
