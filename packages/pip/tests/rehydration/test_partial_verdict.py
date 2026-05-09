"""Partial verdict: some placeholders pass, others fail."""

from __future__ import annotations

from arc_guard_core.observability import NullLogger, NullMetricSink

from arc_guard.rehydration.apply import apply_rehydration
from arc_guard.rehydration.verifier import NullRehydrationVerifier


def test_partial_verdict_substitutes_only_accepted_placeholders() -> None:
    verifier = NullRehydrationVerifier()
    sanitized = "Email [EMAIL_1] and copy [EMAIL_2] tomorrow."
    candidate = "Email [EMAIL_1] and copy `[EMAIL_2]` tomorrow."
    entity_map = {
        "[EMAIL_1]": "alice@acme.com",
        "[EMAIL_2]": "bob@acme.com",
    }
    verdict = verifier.verify(
        sanitized_prompt=sanitized,
        rehydration_candidate=candidate,
        entity_map=entity_map,
    )
    assert verdict.decision == "partial"
    assert verdict.per_placeholder["[EMAIL_1]"] is True
    assert verdict.per_placeholder["[EMAIL_2]"] is False

    rehydrated = apply_rehydration(
        candidate,
        verdict,
        entity_map,
        correlation_id="corr-1",
        decision_id="dec-1",
        logger=NullLogger(),
        metric_sink=NullMetricSink(),
    )
    assert "alice@acme.com" in rehydrated
    # The shifted [EMAIL_2] placeholder stays in place — never rehydrated.
    assert "[EMAIL_2]" in rehydrated
    assert "bob@acme.com" not in rehydrated
