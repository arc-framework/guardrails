"""Contract: lifecycle event field additions are backward-compatible.

Existing constructors continue to work without the new fields (defaults
to None). Wire format renders the new fields as ``null`` when unset.
The closed-union taxonomy stays at 28 types — no new event classes.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

from arc_guard_core.lifecycle import ALL_EVENT_TYPES
from arc_guard_core.lifecycle.events import (
    BackendCalled,
    BackendResponded,
    DeceptionScored,
    JailbreakDetected,
)


def _ts() -> datetime:
    return datetime(2026, 5, 9, 14, 0, 0, tzinfo=UTC)


def test_jailbreak_detected_constructor_works_without_new_field() -> None:
    """Existing callers don't need to pass evidence_reference."""
    ev = JailbreakDetected(
        id="ev-1",
        parent_id=None,
        seq=1,
        ts=_ts(),
        rid="rid-1",
        detector_id="rule-based:1",
        category="prompt-injection",
        confidence=0.9,
    )
    assert ev.evidence_reference is None


def test_jailbreak_detected_field_round_trips_through_asdict() -> None:
    ev = JailbreakDetected(
        id="ev-1",
        parent_id=None,
        seq=1,
        ts=_ts(),
        rid="rid-1",
        detector_id="rule-based:1",
        category="prompt-injection",
        confidence=0.9,
        evidence_reference="rule-based:1/prompt-injection",
    )
    payload = asdict(ev)
    assert payload["evidence_reference"] == "rule-based:1/prompt-injection"


def test_jailbreak_detected_unset_field_serializes_as_none() -> None:
    """Existing wire format is preserved for callers that don't populate
    the new field — the field appears in the dict as None / null."""
    ev = JailbreakDetected(
        id="ev-1",
        parent_id=None,
        seq=1,
        ts=_ts(),
        rid="rid-1",
        detector_id="rule-based:1",
        category="prompt-injection",
        confidence=0.9,
    )
    payload = asdict(ev)
    assert "evidence_reference" in payload
    assert payload["evidence_reference"] is None


def test_deception_scored_marker_counts_default_none() -> None:
    ev = DeceptionScored(
        id="ev-1",
        parent_id=None,
        seq=1,
        ts=_ts(),
        rid="rid-1",
    )
    assert ev.marker_counts is None


def test_deception_scored_marker_counts_round_trips() -> None:
    ev = DeceptionScored(
        id="ev-1",
        parent_id=None,
        seq=1,
        ts=_ts(),
        rid="rid-1",
        marker_counts={"context_drift": 2, "role_assertion": 1},
    )
    payload = asdict(ev)
    assert payload["marker_counts"] == {"context_drift": 2, "role_assertion": 1}


def test_deception_scored_empty_marker_counts_distinct_from_none() -> None:
    """An empty dict means 'computed but no markers fired'; None means
    'not computed for this event'. They are distinct."""
    no_compute = DeceptionScored(
        id="ev-1",
        parent_id=None,
        seq=1,
        ts=_ts(),
        rid="rid-1",
    )
    computed_empty = DeceptionScored(
        id="ev-2",
        parent_id=None,
        seq=2,
        ts=_ts(),
        rid="rid-1",
        marker_counts={},
    )
    assert no_compute.marker_counts is None
    assert computed_empty.marker_counts == {}


def test_backend_called_model_config_snapshot_default_none() -> None:
    ev = BackendCalled(
        id="ev-1",
        parent_id=None,
        seq=1,
        ts=_ts(),
        rid="rid-1",
    )
    assert ev.model_config_snapshot is None


def test_backend_called_model_config_snapshot_round_trips() -> None:
    snap = {
        "provider": "openai",
        "model": "gpt-4o",
        "temperature": 0.5,
        "max_tokens": 100,
    }
    ev = BackendCalled(
        id="ev-1",
        parent_id=None,
        seq=1,
        ts=_ts(),
        rid="rid-1",
        model_config_snapshot=snap,
    )
    assert asdict(ev)["model_config_snapshot"] == snap


def test_backend_responded_token_usage_default_none() -> None:
    ev = BackendResponded(
        id="ev-1",
        parent_id=None,
        seq=1,
        ts=_ts(),
        rid="rid-1",
    )
    assert ev.token_usage is None


def test_backend_responded_token_usage_round_trips() -> None:
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    ev = BackendResponded(
        id="ev-1",
        parent_id=None,
        seq=1,
        ts=_ts(),
        rid="rid-1",
        token_usage=usage,
    )
    assert asdict(ev)["token_usage"] == usage


def test_closed_taxonomy_size() -> None:
    """The closed lifecycle event union ships 29 types: 24 base + 5
    conditional. ``RequestErrored`` is the terminal sister-class to
    ``RequestCompleted``."""
    assert len(ALL_EVENT_TYPES) == 29
