"""Decision record types for arc-guard-core.

A ``DecisionRecord`` is the audit-grade summary of one pipeline run. It is
emitted via the observability hooks (``Logger`` + ``MetricSink``) and
MUST NOT contain raw sensitive payloads. Spans are reported as
``(start, end, length)`` only; replaced content is reported as the replacement
string (e.g. ``[CREDIT_CARD]``), never the original.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from arc_guard_core.policy import RiskBand, TransformSummary
from arc_guard_core.types import RiskLevel


@dataclass(frozen=True)
class FindingSummary:
    """A no-raw-payload summary of one detected finding."""

    entity_type: str
    start: int
    end: int
    length: int
    risk_level: RiskLevel
    inspector: str
    score: float | None = None


@dataclass(frozen=True)
class DecisionRecord:
    """Per-run audit summary. JSON-serializable via ``dataclasses.asdict``.

    The contract test scans serialized records for forbidden substrings
    (any substring of the original input ≥ 8 chars, the original entity
    content). Any leak fails the test.
    """

    correlation_id: str | None
    phase: Literal["pre_process", "post_process"]
    aggregate_action: str
    aggregate_band: RiskBand
    findings: tuple[FindingSummary, ...]
    transforms: tuple[TransformSummary, ...]
    fired_rules: tuple[str, ...]
    refusal_code: str | None
    clarification_present: bool
    latency_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "FindingSummary",
    "DecisionRecord",
]
