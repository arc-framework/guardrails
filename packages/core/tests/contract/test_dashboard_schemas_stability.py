"""Contract: the four dashboard read models are frozen, reject extra
fields, and round-trip through ``model_dump`` ↔ ``model_validate``
without drift.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ValidationError

from arc_guard_core.schemas import (
    RequestDebugEntry,
    RequestDebugPage,
    RequestDecisionEnvelope,
    RequestPage,
    RequestPageFilters,
    RequestSummary,
    RequestWorkspaceManifest,
    WorkspaceResourceLinks,
    WorkspaceResourcesAvailability,
)

_ALL_MODELS = (
    RequestSummary,
    RequestPage,
    RequestPageFilters,
    RequestWorkspaceManifest,
    WorkspaceResourcesAvailability,
    WorkspaceResourceLinks,
    RequestDecisionEnvelope,
    RequestDebugEntry,
    RequestDebugPage,
)


@pytest.mark.parametrize("model_cls", _ALL_MODELS)
def test_all_models_are_frozen(model_cls: type[BaseModel]) -> None:
    assert model_cls.model_config.get("frozen") is True, (
        f"{model_cls.__name__} must be frozen=True"
    )


@pytest.mark.parametrize("model_cls", _ALL_MODELS)
def test_all_models_forbid_extra(model_cls: type[BaseModel]) -> None:
    assert model_cls.model_config.get("extra") == "forbid", (
        f"{model_cls.__name__} must reject extra fields"
    )


def _sample_summary() -> RequestSummary:
    return RequestSummary(
        rid="01JABC0EVT01",
        started_at=datetime(2026, 5, 8, 14, 0, 0, tzinfo=UTC),
        last_event_at=datetime(2026, 5, 8, 14, 0, 0, 842_000, tzinfo=UTC),
        status="completed",
        final_action="block",
        max_risk=0.91,
        duration_ms=842,
        refusal_code="PII_LEAK",
        decision_id="dec_01JABC",
        live=False,
        stage="report",
    )


def test_request_summary_roundtrip() -> None:
    summary = _sample_summary()
    dumped = summary.model_dump()
    rehydrated = RequestSummary.model_validate(dumped)
    assert summary == rehydrated


def test_request_summary_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        RequestSummary.model_validate(
            {**_sample_summary().model_dump(), "ghost_field": True}
        )


def test_request_summary_rejects_unknown_stage() -> None:
    """The stage field is a Literal; arbitrary strings must be rejected."""
    with pytest.raises(ValidationError):
        RequestSummary.model_validate(
            {**_sample_summary().model_dump(), "stage": "telekinesis"}
        )


def test_request_workspace_manifest_roundtrip() -> None:
    manifest = RequestWorkspaceManifest(
        summary=_sample_summary(),
        resources=WorkspaceResourcesAvailability(
            lifecycle=True, decision=True, debug=True, live_stream=False
        ),
        links=WorkspaceResourceLinks(
            lifecycle="/lifecycle/01JABC0EVT01",
            decision="/requests/01JABC0EVT01/decision",
            debug="/requests/01JABC0EVT01/debug",
            live_stream="/events?rid=01JABC0EVT01",
        ),
    )
    rehydrated = RequestWorkspaceManifest.model_validate(manifest.model_dump())
    assert rehydrated == manifest


def test_request_decision_envelope_roundtrip() -> None:
    envelope = RequestDecisionEnvelope(
        rid="01JABC0EVT01",
        decision_id="dec_01JABC",
        recorded_at=datetime(2026, 5, 8, 14, 0, 0, 842_000, tzinfo=UTC),
        decision={"action": "block", "score": 0.91, "rules": ["PII_LEAK"]},
        payload_size_bytes=4218,
    )
    rehydrated = RequestDecisionEnvelope.model_validate(envelope.model_dump())
    assert rehydrated == envelope


def test_request_debug_entry_roundtrip() -> None:
    entry = RequestDebugEntry(
        rid="01JABC0EVT01",
        seq=1,
        ts=datetime(2026, 5, 8, 14, 0, 0, 12_000, tzinfo=UTC),
        channel="arc_guard.pipeline",
        severity="DEBUG",
        message="stage=classify finding=EMAIL_ADDRESS confidence=0.97",
        metadata={"stage": "classify", "finding_count": 1},
    )
    rehydrated = RequestDebugEntry.model_validate(entry.model_dump())
    assert rehydrated == entry


def test_request_debug_entry_rejects_unknown_severity() -> None:
    with pytest.raises(ValidationError):
        RequestDebugEntry.model_validate(
            {
                "rid": "01JABC0EVT01",
                "seq": 1,
                "ts": datetime(2026, 5, 8, tzinfo=UTC),
                "channel": "arc_guard.pipeline",
                "severity": "VERBOSE",  # not in the allowed set
                "message": "x",
                "metadata": {},
            }
        )


def test_request_debug_page_roundtrip_with_cursor() -> None:
    page = RequestDebugPage(
        rid="01JABC0EVT01",
        items=(),
        next_cursor="eyJzZXEiOjEsInJpZCI6IjAxSkFCQzBFVlQwMSJ9",
        page_size=100,
    )
    rehydrated = RequestDebugPage.model_validate(page.model_dump())
    assert rehydrated == page


def test_request_page_filters_default_empty_tuples() -> None:
    """The filter echo defaults to empty tuples (frozen-friendly), not lists."""
    f = RequestPageFilters()
    assert f.status == ()
    assert f.action == ()
    assert f.risk_band == ()
    assert f.rid_prefix is None
    assert f.since is None
    assert f.until is None


def test_frozen_models_reject_assignment() -> None:
    """Sanity check: frozen really is frozen."""
    summary = _sample_summary()
    with pytest.raises(ValidationError):
        summary.live = True  # type: ignore[misc]
