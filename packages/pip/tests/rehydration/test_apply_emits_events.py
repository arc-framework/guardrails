"""``apply_rehydration`` emits the documented applied / rejected events."""

from __future__ import annotations

from arc_guard_core.protocols.rehydration_verifier import RehydrationVerdict

from arc_guard.observability import (
    RecordingLogger,
    RecordingMetricSink,
)
from arc_guard.rehydration.apply import apply_rehydration


def test_accept_verdict_emits_applied_event() -> None:
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()

    out = apply_rehydration(
        "Email [EMAIL] tomorrow.",
        RehydrationVerdict(decision="accept", reason="all_checks_passed"),
        entity_map={"[EMAIL]": "alice@acme.com"},
        correlation_id="corr-1",
        decision_id="dec-1",
        logger=logger,
        metric_sink=metric_sink,
    )
    assert out == "Email alice@acme.com tomorrow."

    applied = [e for e in logger.captured_events if e.name == "guard.rehydration.applied"]
    assert len(applied) == 1
    assert applied[0].fields["placeholders_total"] == 1
    assert applied[0].fields["placeholders_accepted"] == 1

    rejected = [e for e in logger.captured_events if e.name == "guard.rehydration.rejected"]
    assert rejected == []

    counters = [
        m for m in metric_sink.captured_metrics
        if m.name == "arc_guardrails.rehydration.verdict"
    ]
    assert len(counters) == 1
    assert counters[0].attributes["decision"] == "accept"


def test_reject_verdict_emits_rejected_event() -> None:
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()

    out = apply_rehydration(
        "Email [EMAIL] tomorrow.",
        RehydrationVerdict(decision="reject", reason="invented_placeholder"),
        entity_map={"[EMAIL]": "alice@acme.com"},
        correlation_id="corr-1",
        decision_id="dec-1",
        logger=logger,
        metric_sink=metric_sink,
    )
    # Reject keeps placeholders.
    assert out == "Email [EMAIL] tomorrow."

    rejected = [e for e in logger.captured_events if e.name == "guard.rehydration.rejected"]
    assert len(rejected) == 1
    assert rejected[0].fields["reason"] == "invented_placeholder"
    assert rejected[0].fields["placeholders_accepted"] == 0

    applied = [e for e in logger.captured_events if e.name == "guard.rehydration.applied"]
    assert applied == []
