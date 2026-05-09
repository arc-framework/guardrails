"""Contract: new optional payload-text fields default to ``None`` and
round-trip cleanly through ``asdict`` + the SQLite serializer.

The fields are populated only when ``ServiceSettings.lifecycle_capture_payloads``
is true; with capture off they MUST be ``None``. The dashboard's Diff/Replay
tab depends on these fields existing on the wire format with ``null`` as the
unset value (not absent).

Also covers the new ``RequestErrored`` terminal event class — defaults,
round-trip, and union-membership.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, get_args

import pytest

from arc_guard_core.lifecycle import (
    LifecycleEvent,
    PayloadRewritten,
    RehydrationVerified,
    RequestErrored,
    ResponseAssembled,
    SanitizationApplied,
    StrategyExecuted,
)


def _ts() -> datetime:
    return datetime(2026, 5, 9, 14, 0, 0, tzinfo=UTC)


def _common() -> dict[str, Any]:
    return {
        "id": "ev-1",
        "parent_id": None,
        "seq": 1,
        "ts": _ts(),
        "rid": "rid-abc",
    }


# (event_class, before_field, after_field). before_field is None when only
# the after-side text exists for that event (ResponseAssembled).
EVENT_FIELDS: list[tuple[type, str | None, str]] = [
    (StrategyExecuted, "text_before", "text_after"),
    (PayloadRewritten, "text_before", "text_after"),
    (RehydrationVerified, "text_before", "text_after"),
    (SanitizationApplied, "text_before", "text_after"),
]


@pytest.mark.parametrize("event_cls,before_field,after_field", EVENT_FIELDS)
def test_text_fields_default_to_none(
    event_cls: type, before_field: str | None, after_field: str
) -> None:
    ev = event_cls(**_common())
    if before_field is not None:
        assert getattr(ev, before_field) is None
    assert getattr(ev, after_field) is None


@pytest.mark.parametrize("event_cls,before_field,after_field", EVENT_FIELDS)
def test_text_fields_accept_strings_and_round_trip(
    event_cls: type, before_field: str | None, after_field: str
) -> None:
    kwargs: dict[str, Any] = dict(_common())
    if before_field is not None:
        kwargs[before_field] = "hello"
    kwargs[after_field] = "world"
    ev = event_cls(**kwargs)
    payload = asdict(ev)
    if before_field is not None:
        assert payload[before_field] == "hello"
    assert payload[after_field] == "world"
    payload["ts"] = payload["ts"].isoformat()
    json.dumps(payload, default=list)


def test_response_assembled_response_text_default_and_round_trip() -> None:
    ev = ResponseAssembled(**_common())
    assert ev.response_text is None
    ev2 = ResponseAssembled(**_common(), response_text="assistant reply")
    payload = asdict(ev2)
    assert payload["response_text"] == "assistant reply"


def test_request_errored_defaults() -> None:
    ev = RequestErrored(**_common())
    assert ev.reason == "stale_live_sweep"
    assert ev.terminated_by == ""
    assert ev.last_event_seq == 0


def test_request_errored_round_trip() -> None:
    ev = RequestErrored(
        **_common(),
        reason="pipeline_exception",
        terminated_by="pipeline.exception_handler",
        last_event_seq=14,
    )
    payload = asdict(ev)
    assert payload["reason"] == "pipeline_exception"
    assert payload["terminated_by"] == "pipeline.exception_handler"
    assert payload["last_event_seq"] == 14
    payload["ts"] = payload["ts"].isoformat()
    json.dumps(payload, default=list)


def test_request_errored_in_lifecycle_event_union() -> None:
    """The discriminated union must include ``RequestErrored`` so type
    narrowing works for sinks that match on union members."""
    union_members = set(get_args(LifecycleEvent))
    assert RequestErrored in union_members
