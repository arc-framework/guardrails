"""Pydantic models for the lifecycle replay endpoint.

The `LifecycleEnvelope` is the JSON wire format returned by
`GET /lifecycle/{rid}`. It carries the request's full ordered event list
plus capture metadata so a dashboard can reconstruct the DAG without a
second round-trip.

Errors use a separate `LifecycleErrorEnvelope` shape; see the contract at
`specs/010-lifecycle-sink/contracts/http-lifecycle-replay.md`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ServedFromTier = Literal["ring-buffer", "sqlite", "external", "composite-fallthrough"]


class LifecycleEnvelope(BaseModel):
    """Successful lookup response — full event tree for one rid."""

    model_config = ConfigDict(extra="allow")

    rid: str = Field(description="The request correlation id echoed from the path segment.")
    captured_at: datetime = Field(
        description="Timestamp of the FIRST event captured for this rid (typically RequestStarted)."
    )
    served_from: ServedFromTier = Field(
        description="Which configured sink tier served the response. Helpful for debugging."
    )
    phases: list[Literal["pre_process", "post_process"]] = Field(
        description="Phase boundaries observed for this rid. Empty if the request was rejected before guard ran."
    )
    events: list[dict[str, Any]] = Field(
        description=(
            "Full ordered event list, sorted by `seq` ascending. Each event is a JSON object "
            "matching the typed shape in `data-model.md` §2-§3."
        )
    )


class LifecycleErrorEnvelope(BaseModel):
    """Error response shape for 4xx/5xx replies from `/lifecycle/{rid}`."""

    model_config = ConfigDict(extra="allow")

    code: Literal["rid_malformed", "rid_not_found", "lifecycle_disabled", "lifecycle_lookup_failed"]
    message: str
    rid: str | None = None


__all__ = ["LifecycleEnvelope", "LifecycleErrorEnvelope", "ServedFromTier"]
