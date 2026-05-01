"""Core typed models for arc-guard-core.

All types are immutable (frozen dataclasses or enums) so the pipeline is safe
to share across threads / coroutines and findings can be accumulated without
mutation.

This module is part of the contract layer. Field-level descriptions and
validation rules live in ``specs/002-rewrite-foundation/data-model.university``.
The contract test suite under ``tests/contract/`` snapshots these types and
fails on incompatible changes.
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
        source: ``"input"`` (user prompt) or ``"output"`` (model response).
            Some inspectors only run on ``source="input"``.
        user_id: Optional identifier for per-user audit trails.
        session_id: Optional conversation session identifier.
        correlation_id: Trace-correlation identifier. Hooked into the
            ``Tracer`` protocol when provided.
        metadata: Arbitrary key-value pairs for downstream use.
    """

    source: Literal["input", "output"] = "input"
    user_id: str | None = None
    session_id: str | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GuardInput:
    """Input to the guard pipeline.

    Args:
        text: The text to inspect and potentially transform.
        context: Contextual metadata for the inspection.
        policy_hints: Caller-supplied hints (e.g. ``"strict"``, ``"lite"``)
            consumed by the policy router. Unrecognized hints are ignored.
            Frozen to keep the input hashable.
    """

    text: str
    context: GuardContext = field(default_factory=GuardContext)
    policy_hints: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class Finding:
    """A single detection result from an inspector.

    Args:
        entity_type: Normalised entity label, e.g. ``"CREDIT_CARD"``,
            ``"INJECTION"``, ``"EMPLOYEE_NAME"``.
        start: Character offset in the original text (inclusive). ``>= 0``.
        end: Character offset (exclusive). ``> start``.
        risk_level: Severity of this finding.
        inspector: Name of the inspector that produced this finding.
        score: Optional confidence score in ``[0.0, 1.0]``.
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
class PolicyDecision:
    """A routing decision applied to one or more findings.

    Args:
        finding_ids: Indices into ``GuardResult.findings`` this decision applies to.
        strategy: Strategy identifier (``"redact"``, ``"hash"``, ``"block"``,
            ``"tokenize"``, or a registered custom name).
        severity: Aggregated severity for the decision.
        rationale: Short, human-readable rationale.
        metadata: Strategy-specific extras.
    """

    finding_ids: tuple[int, ...]
    strategy: str
    severity: RiskLevel
    rationale: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RefusalEnvelope:
    """Structured refusal returned when the system blocks or restricts.

    Args:
        code: Stable, machine-readable refusal code from ``RefusalCode``.
        trigger: What triggered the refusal (e.g. ``"jailbreak"``, ``"pii_critical"``).
        policy: Identifier of the policy that fired.
        decisions: Decisions that produced this refusal, in order.
        human_message: Human-readable explanation suitable for direct display.
        next_steps: Optional list of suggested user actions.
        metadata: Extension point.
    """

    code: str
    trigger: str
    policy: str
    human_message: str
    decisions: tuple[PolicyDecision, ...] = field(default_factory=tuple)
    next_steps: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClarificationRequest:
    """Structured ask-for-rephrase returned when the policy classifies a run
    as ambiguous and ``clarification_enabled=True``.

    Args:
        suggested_rephrase: Human-readable rephrase the caller should ask
            the user for. Non-empty.
        next_steps: Optional supporting bullets the caller can render.
        triggering_rule_id: ``PolicyRule.id`` that classified the run as
            ambiguous, when known.
        metadata: Extension point.
    """

    suggested_rephrase: str
    next_steps: tuple[str, ...] = field(default_factory=tuple)
    triggering_rule_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.suggested_rephrase:
            raise ValueError("ClarificationRequest.suggested_rephrase must be non-empty")


@dataclass(frozen=True)
class GuardResult:
    """Output from the guard pipeline.

    Args:
        text: Possibly transformed text. Empty when ``action == "block"``.
        action: Aggregate action chosen by the pipeline.
        findings: All detections across all inspectors.
        decisions: Per-finding decisions populated by the policy router.
        refusal: Set when ``action == "block"`` and on HIGH-band partial
            refusals (sanitized text plus a refusal envelope describing what
            was withheld).
        clarification: Set when policy classified the run as ambiguous and
            ``clarification_enabled=True``. Mutually exclusive with
            ``action == "block"``.
        bypass_reason: Set when the pipeline was short-circuited.
            ``"disabled"`` — guard is off.
            ``"error"`` — an inspector raised; the pipeline fell through fail-open.
            ``None`` — pipeline ran cleanly.
        phase: ``"pre_process"`` (input) or ``"post_process"`` (output).
    """

    text: str
    action: Literal["pass", "redact", "hash", "block", "tokenize"] = "pass"
    findings: tuple[Finding, ...] = field(default_factory=tuple)
    decisions: tuple[PolicyDecision, ...] = field(default_factory=tuple)
    refusal: RefusalEnvelope | None = None
    clarification: ClarificationRequest | None = None
    bypass_reason: Literal["disabled", "error", None] = None
    phase: Literal["pre_process", "post_process"] = "pre_process"

    def __post_init__(self) -> None:
        # Clarification is a recovery path; it is mutually exclusive with a
        # hard block. Callers either ask the user to rephrase or refuse.
        if self.clarification is not None and self.action == "block":
            raise ValueError(
                "GuardResult.clarification cannot be set when action='block'"
            )

    @property
    def is_clean(self) -> bool:
        """True when no findings were produced."""
        return len(self.findings) == 0

    @property
    def max_risk(self) -> RiskLevel:
        """Highest risk level across all findings, or ``NONE`` if clean."""
        if self.is_clean:
            return RiskLevel.NONE
        return max(f.risk_level for f in self.findings)


@dataclass(frozen=True)
class EntityDefinition:
    """A custom entity type registered with the EntityRegistry.

    Args:
        name: Unique label, e.g. ``"AADHAAR"``, ``"NZ_IRD"``, ``"EMPLOYEE_NAME"``.
        category: Broad category for grouping: ``"PII"``, ``"PCI"``, ``"ENTERPRISE"``,
            ``"CUSTOM"``.
        pattern: Optional compiled regex to detect this entity.
        recognizer: Optional presidio ``PatternRecognizer`` for richer detection.
            Typed as ``Any`` so ``arc_guard_core`` does not import presidio.
    """

    name: str
    category: str
    pattern: re.Pattern[str] | None = None
    recognizer: Any | None = None


__all__ = [
    "RiskLevel",
    "GuardContext",
    "GuardInput",
    "Finding",
    "PolicyDecision",
    "RefusalEnvelope",
    "ClarificationRequest",
    "GuardResult",
    "EntityDefinition",
]
