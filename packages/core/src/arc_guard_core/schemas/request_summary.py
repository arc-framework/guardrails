"""Request-summary read models for the dashboard explorer + workspace.

Six pydantic v2 models. All frozen, all reject extra fields. Field types
mirror the SQLite columns documented in data-model.md §1.1; the `stage`
Literal is bound to ``arc_guard_core.stages.STAGE_DESCRIPTORS`` and a
contract test enforces drift detection.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

# Bound to STAGE_DESCRIPTORS (12 names from the post-006 stage set).
# Drift detection enforced by
# packages/core/tests/contract/test_request_summary_shape.py.
StageName = Literal[
    "validate",
    "defend",
    "classify",
    "deception_inspect",
    "sanitize",
    "route",
    "execute",
    "refusal",
    "verify",
    "rehydrate",
    "decision_emit",
    "report",
]


RequestStatus = Literal["live", "completed", "errored"]


FinalAction = Literal["pass", "block", "redact", "clarify", "refuse"]


RiskBand = Literal["low", "med", "high"]


class RequestSummary(BaseModel):
    """One row in the explorer table."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rid: str
    started_at: datetime
    last_event_at: datetime
    status: RequestStatus
    final_action: FinalAction | None = None
    max_risk: float | None = None
    duration_ms: int | None = None
    refusal_code: str | None = None
    decision_id: str | None = None
    live: bool
    stage: StageName | None = None


class RequestPageFilters(BaseModel):
    """Echo of the effective filters the server applied to a page lookup."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    since: datetime | None = None
    until: datetime | None = None
    status: tuple[RequestStatus, ...] = ()
    action: tuple[FinalAction, ...] = ()
    risk_band: tuple[RiskBand, ...] = ()
    rid_prefix: str | None = None


class RequestPage(BaseModel):
    """Paginated response envelope for ``GET /requests``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    items: tuple[RequestSummary, ...]
    page: int
    page_size: int
    total: int
    has_more: bool
    filters: RequestPageFilters


class WorkspaceResourcesAvailability(BaseModel):
    """Boolean availability flags for the four workspace resources."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lifecycle: bool
    decision: bool
    debug: bool
    live_stream: bool


class WorkspaceResourceLinks(BaseModel):
    """Pre-built path strings for the four workspace resources."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lifecycle: str
    decision: str
    debug: str
    live_stream: str


class RequestWorkspaceManifest(BaseModel):
    """Returned by ``GET /requests/{rid}`` — summary plus resource manifest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: RequestSummary
    resources: WorkspaceResourcesAvailability
    links: WorkspaceResourceLinks


__all__ = [
    "FinalAction",
    "RequestPage",
    "RequestPageFilters",
    "RequestStatus",
    "RequestSummary",
    "RequestWorkspaceManifest",
    "RiskBand",
    "StageName",
    "WorkspaceResourceLinks",
    "WorkspaceResourcesAvailability",
]
