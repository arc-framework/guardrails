"""Dashboard read models for the operator data plane.

These pydantic models back the four new HTTP routes in
``arc_guard_service.transport.requests`` and the additive resource
manifest returned by ``GET /requests/{rid}``.

Submodules:

- ``request_summary`` — explorer table row + page envelope + workspace manifest
- ``request_decision`` — DecisionRecord retrieval envelope
- ``request_debug`` — debug-entry envelope + cursor pagination helpers

All models are pydantic v2 ``BaseModel`` with ``frozen=True, extra="forbid"``
for stable wire format. The submodules import only from ``pydantic`` plus
stdlib (``datetime``, ``typing``, ``base64``, ``json``); a contract test
asserts this provider-neutrality invariant.
"""

from arc_guard_core.schemas.request_debug import (
    RequestDebugEntry,
    RequestDebugPage,
    decode_debug_cursor,
    encode_debug_cursor,
)
from arc_guard_core.schemas.request_decision import RequestDecisionEnvelope
from arc_guard_core.schemas.request_summary import (
    RequestPage,
    RequestPageFilters,
    RequestSummary,
    RequestWorkspaceManifest,
    WorkspaceResourceLinks,
    WorkspaceResourcesAvailability,
)

# Type aliases (StageName, RequestStatus, FinalAction, RiskBand, DebugSeverity)
# stay module-local — `arc_guard_core.policy.RiskBand` already occupies the
# top-level name and the aliases are used only inside the model definitions.
__all__ = [
    "RequestDebugEntry",
    "RequestDebugPage",
    "RequestDecisionEnvelope",
    "RequestPage",
    "RequestPageFilters",
    "RequestSummary",
    "RequestWorkspaceManifest",
    "WorkspaceResourceLinks",
    "WorkspaceResourcesAvailability",
    "decode_debug_cursor",
    "encode_debug_cursor",
]
