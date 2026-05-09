"""Replay endpoint — `GET /lifecycle/{rid}` returns the full ordered event
list captured for one request as a JSON envelope.

Reads from the configured `LifecycleSink`. When the sink is a composite
(ring buffer + persistent store), tier fall-through is the sink's
responsibility; this endpoint just calls `sink.query(rid)` and serializes
whatever non-None list comes back. The `served_from` envelope field carries
the tier name the sink reports (or `composite-fallthrough` for unknown
multi-child sinks).

Errors follow the contract at
`specs/010-lifecycle-sink/contracts/http-lifecycle-replay.md`.
"""

from __future__ import annotations

import importlib
import logging
import re
import time
from dataclasses import asdict
from datetime import datetime
from typing import Any

from arc_guard_core.lifecycle import LifecycleEvent, LifecycleSink

from arc_guard_service.schemas.lifecycle import (
    LifecycleEnvelope,
    LifecycleErrorEnvelope,
    ServedFromTier,
)
from arc_guard_service.settings import ServiceSettings

_LOG = logging.getLogger("arc-guard.api.lifecycle")

# rid format: ASCII-safe, 1–64 chars, identifier-shaped. Loose enough to
# accept upstream-generated values (uuid, ulid, x-request-id headers from
# load balancers) while rejecting path-traversal / SSRF attempts.
_RID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _event_to_json_dict(event: LifecycleEvent) -> dict[str, Any]:
    """Serialize a LifecycleEvent dataclass to a JSON-friendly dict.

    Mirrors `transport/events.py:_event_to_json_dict` but lives separately to
    avoid importing the SSE module's heavier surface (subscriber registry).
    Both serializations MUST stay byte-identical — a contract test in the
    test suite asserts this.
    """
    d = asdict(event)
    d["event_type"] = type(event).event_type
    for k, v in list(d.items()):
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif isinstance(v, tuple):
            d[k] = list(v)
    return d


def _phases_observed(events: list[LifecycleEvent]) -> list[str]:
    phases: list[str] = []
    seen: set[str] = set()
    for ev in events:
        et = type(ev).event_type
        if et == "PreProcessStarted" and "pre_process" not in seen:
            phases.append("pre_process")
            seen.add("pre_process")
        elif et == "PostProcessStarted" and "post_process" not in seen:
            phases.append("post_process")
            seen.add("post_process")
    return phases


def _tier_label(sink: LifecycleSink) -> ServedFromTier:
    """Best-effort tier identification from the sink class name.

    Returns one of the documented `ServedFromTier` literal values. Unknown
    sinks (operator-owned externals or composites without a `last_served_from`
    attribute) collapse to `composite-fallthrough`.
    """
    last = getattr(sink, "last_served_from", None)
    if last in ("ring-buffer", "sqlite", "external"):
        return last  # type: ignore[return-value]
    cls_name = type(sink).__name__
    if "Ring" in cls_name:
        return "ring-buffer"
    if "Sqlite" in cls_name:
        return "sqlite"
    return "composite-fallthrough"


def build_lifecycle_router(
    *,
    settings: ServiceSettings,
    lifecycle_sink: LifecycleSink,
) -> Any:
    """Construct the FastAPI router exposing `GET /lifecycle/{rid}`."""
    fastapi = importlib.import_module("fastapi")
    JSONResponse = fastapi.responses.JSONResponse  # noqa: N806
    APIRouter = fastapi.APIRouter  # noqa: N806

    router = APIRouter()

    @router.get(
        "/lifecycle/{rid}",
        response_model=LifecycleEnvelope,
        summary="Replay the full lifecycle event tree for a past request",
        tags=["lifecycle"],
        responses={
            400: {
                "model": LifecycleErrorEnvelope,
                "description": "Malformed rid (failed format validation).",
            },
            404: {
                "model": LifecycleErrorEnvelope,
                "description": "rid not found in any configured lifecycle store.",
            },
            503: {
                "model": LifecycleErrorEnvelope,
                "description": "Lifecycle observation is disabled.",
            },
        },
    )
    async def lifecycle_replay(rid: str) -> Any:
        if not settings.lifecycle_enabled:
            envelope = LifecycleErrorEnvelope(
                code="lifecycle_disabled",
                message="Lifecycle observation is disabled in this deployment.",
                rid=rid,
            )
            return JSONResponse(
                status_code=503,
                content=envelope.model_dump(),
            )

        if not _RID_PATTERN.match(rid):
            envelope = LifecycleErrorEnvelope(
                code="rid_malformed",
                message="rid must match [A-Za-z0-9._-]{1,64}",
                rid=rid,
            )
            return JSONResponse(
                status_code=400,
                content=envelope.model_dump(),
            )

        t0 = time.perf_counter()
        try:
            events = await lifecycle_sink.query(rid)
        except Exception as exc:  # pragma: no cover — sink failure path
            _LOG.warning("lifecycle sink query failed for rid=%s: %s", rid, exc)
            envelope = LifecycleErrorEnvelope(
                code="lifecycle_lookup_failed",
                message=f"sink query raised: {type(exc).__name__}",
                rid=rid,
            )
            return JSONResponse(
                status_code=503,
                content=envelope.model_dump(),
            )

        if not events:
            envelope = LifecycleErrorEnvelope(
                code="rid_not_found",
                message="rid not found in any configured lifecycle store",
                rid=rid,
            )
            return JSONResponse(
                status_code=404,
                content=envelope.model_dump(),
                headers={"x-lifecycle-tier": _tier_label(lifecycle_sink)},
            )

        envelope_payload = LifecycleEnvelope(
            rid=rid,
            captured_at=events[0].ts,
            served_from=_tier_label(lifecycle_sink),
            phases=_phases_observed(events),
            events=[_event_to_json_dict(ev) for ev in events],
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        _LOG.info(
            "lifecycle lookup rid=%s served_from=%s events=%d elapsed_ms=%.1f",
            rid,
            envelope_payload.served_from,
            len(events),
            elapsed_ms,
        )
        return JSONResponse(
            status_code=200,
            content=envelope_payload.model_dump(mode="json"),
            headers={"x-lifecycle-tier": envelope_payload.served_from},
        )

    return router


__all__ = ["build_lifecycle_router"]
