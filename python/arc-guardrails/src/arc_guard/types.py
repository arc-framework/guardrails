"""Core data types for arc-guard.

All types are immutable (frozen dataclasses or enums) to make the pipeline
thread-safe and to allow findings to be safely accumulated across inspectors.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Literal


class RiskLevel(IntEnum):
    """Ordered risk severity. Higher value = higher risk."""

    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass(frozen=True)
class GuardContext:
    """Contextual metadata attached to a guard call.

    Args:
        source: "input" (user prompt) or "output" (model response).
            InjectionInspector only runs on source="input".
        user_id: Optional identifier for per-user audit trails.
        session_id: Optional conversation session identifier.
        metadata: Arbitrary key-value pairs for downstream use.
    """

    source: Literal["input", "output"] = "input"
    user_id: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GuardInput:
    """Input to the guard pipeline.

    Args:
        text: The text to inspect and potentially transform.
        context: Contextual metadata for the inspection.
    """

    text: str
    context: GuardContext = field(default_factory=GuardContext)


@dataclass(frozen=True)
class Finding:
    """A single detection result from an inspector.

    Args:
        entity_type: Normalised entity label, e.g. "CREDIT_CARD", "INJECTION".
        start: Character offset in the original text (inclusive).
        end: Character offset in the original text (exclusive).
        risk_level: Severity of this finding.
        inspector: Name of the inspector that produced this finding.
        score: Optional confidence score in [0.0, 1.0].
        metadata: Arbitrary extra data from the inspector.
    """

    entity_type: str
    start: int
    end: int
    risk_level: RiskLevel
    inspector: str
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def span(self) -> str:
        """Slice notation for the detected span: useful for logging."""
        return f"[{self.start}:{self.end}]"


@dataclass(frozen=True)
class GuardResult:
    """Output from the guard pipeline.

    Args:
        text: Potentially transformed text (redacted, hashed, or empty if blocked).
        action: What the pipeline did: "pass", "redact", "hash", or "block".
        findings: All detections across all inspectors.
        bypass_reason: Set when the pipeline was short-circuited.
            "disabled" — guard is off (GUARD_ENABLED=false).
            "error"    — an inspector raised; pipeline fell through fail-open.
            None       — pipeline ran cleanly.
        phase: "pre_process" (input) or "post_process" (output).
    """

    text: str
    action: Literal["pass", "redact", "hash", "block"] = "pass"
    findings: tuple[Finding, ...] = field(default_factory=tuple)
    bypass_reason: Literal["disabled", "error", None] = None
    phase: Literal["pre_process", "post_process"] = "pre_process"

    @property
    def is_clean(self) -> bool:
        """True when no findings were produced."""
        return len(self.findings) == 0

    @property
    def max_risk(self) -> RiskLevel:
        """Highest risk level across all findings, or NONE if clean."""
        if self.is_clean:
            return RiskLevel.NONE
        return max(f.risk_level for f in self.findings)


@dataclass(frozen=True)
class EntityDefinition:
    """A custom entity type registered with the EntityRegistry.

    Args:
        name: Unique label, e.g. "AADHAAR", "NZ_IRD".
        category: Broad category for grouping: "PII", "PCI", "CUSTOM".
        pattern: Optional compiled regex to detect this entity.
        recognizer: Optional presidio PatternRecognizer for richer detection.
    """

    name: str
    category: str
    pattern: re.Pattern[str] | None = None
    recognizer: Any | None = None  # presidio PatternRecognizer
