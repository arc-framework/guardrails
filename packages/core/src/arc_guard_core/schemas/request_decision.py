"""DecisionRecord retrieval envelope.

Wraps the persisted ``DecisionRecord`` payload (whose schema is owned by
the sanitization-policy core spec) in a stable envelope so the dashboard
client doesn't depend on that internal payload shape directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class RequestDecisionEnvelope(BaseModel):
    """Returned by ``GET /requests/{rid}/decision``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rid: str
    decision_id: str
    recorded_at: datetime
    decision: dict[str, Any]
    payload_size_bytes: int


__all__ = ["RequestDecisionEnvelope"]
