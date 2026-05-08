"""Lifecycle event taxonomy — typed, frozen dataclasses forming a closed
tagged union over `LifecycleEvent`.

Twenty-eight types ship: twenty-three base events (always emitted when their
upstream condition is met) plus five conditional events (only when an
optional component is wired or an exceptional condition fires).

Every event carries the universal fields (`id`, `parent_id`, `seq`, `ts`,
`rid`) plus type-specific fields. Cross-reference fields point at another
event's `id`, capturing causal relationships beyond the parent chain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar, Literal


@dataclass(frozen=True)
class LifecycleEventBase:
    """Fields every LifecycleEvent carries.

    Concrete event classes inherit and add type-specific fields. The class-level
    `event_type` constant supplies the wire-format discriminator.
    """

    id: str
    parent_id: str | None
    seq: int
    ts: datetime
    rid: str


# ---------------------------------------------------------------------------
# Base events (23)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RequestStarted(LifecycleEventBase):
    event_type: ClassVar[str] = "RequestStarted"
    route: str = ""
    model: str | None = None
    msg_count: int | None = None
    input_size_bytes: int = 0
    # Populated only when the configured PayloadCapturePolicy permits raw
    # input capture (off by default). Security-sensitive — see policy docs.
    raw_input: str | None = None


@dataclass(frozen=True)
class PreProcessStarted(LifecycleEventBase):
    event_type: ClassVar[str] = "PreProcessStarted"
    correlation_id: str = ""
    decision_id: str = ""


@dataclass(frozen=True)
class PostProcessStarted(LifecycleEventBase):
    event_type: ClassVar[str] = "PostProcessStarted"
    correlation_id: str = ""
    decision_id: str = ""


@dataclass(frozen=True)
class PreProcessCompleted(LifecycleEventBase):
    event_type: ClassVar[str] = "PreProcessCompleted"
    action: str = "pass"
    blocked: bool = False
    total_duration_ms: float = 0.0


@dataclass(frozen=True)
class PostProcessCompleted(LifecycleEventBase):
    event_type: ClassVar[str] = "PostProcessCompleted"
    action: str = "pass"
    blocked: bool = False
    total_duration_ms: float = 0.0


@dataclass(frozen=True)
class StageRan(LifecycleEventBase):
    event_type: ClassVar[str] = "StageRan"
    stage: Literal[
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
    ] = "validate"
    duration_ms: float = 0.0
    status: Literal["ok", "err", "skipped"] = "ok"


@dataclass(frozen=True)
class IntentCaptured(LifecycleEventBase):
    event_type: ClassVar[str] = "IntentCaptured"
    encoder_id: str = "null:1"
    intent_size_bytes: int = 0


@dataclass(frozen=True)
class InspectorRan(LifecycleEventBase):
    event_type: ClassVar[str] = "InspectorRan"
    name: str = ""
    duration_ms: float = 0.0
    findings_count: int = 0


@dataclass(frozen=True)
class FindingProduced(LifecycleEventBase):
    event_type: ClassVar[str] = "FindingProduced"
    entity_type: str = ""
    span: tuple[int, int] = (0, 0)
    score: float = 0.0
    risk_level: int = 1
    inspector: str = ""


@dataclass(frozen=True)
class JailbreakDetected(LifecycleEventBase):
    event_type: ClassVar[str] = "JailbreakDetected"
    detector_id: str = "rule-based:1"
    category: str = ""
    confidence: float = 0.0


@dataclass(frozen=True)
class DeceptionScored(LifecycleEventBase):
    event_type: ClassVar[str] = "DeceptionScored"
    score_value: float | None = None
    score_sentinel: str | None = "not_measured"
    band: Literal["not_measured", "low", "medium", "high"] = "not_measured"
    turn_count: int = 1
    prior_score: float | None = None
    drift_delta: float | None = None


@dataclass(frozen=True)
class FidelityScored(LifecycleEventBase):
    event_type: ClassVar[str] = "FidelityScored"
    score_value: float | None = None
    score_sentinel: str | None = "not_measured"
    band: Literal["not_measured", "low", "medium", "high"] = "not_measured"


@dataclass(frozen=True)
class SanitizationApplied(LifecycleEventBase):
    """One per placeholder produced by the sanitize stage.

    `finding_id` cross-references the FindingProduced.id that drove this sanitization.
    Distinct from the request-level summary `PlaceholderMapBuilt` (conditional).
    """

    event_type: ClassVar[str] = "SanitizationApplied"
    entity_type: str = ""
    placeholder: str = ""
    span: tuple[int, int] = (0, 0)
    finding_id: str = ""
    # Populated only when the configured PayloadCapturePolicy permits
    # sanitized capture (off by default). Carries the post-sanitization
    # text — placeholder substitutions already applied.
    text_after: str | None = None


@dataclass(frozen=True)
class PolicyResolved(LifecycleEventBase):
    """One per route stage execution. Summarizes the final action picked.

    Distinct from the conditional, per-rule `PolicyRuleEvaluated`.
    """

    event_type: ClassVar[str] = "PolicyResolved"
    max_risk: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "LOW"
    resolved_action: str = "pass"
    router: str = "default"


@dataclass(frozen=True)
class StrategyExecuted(LifecycleEventBase):
    """One per strategy invocation in the execute stage.

    `finding_id` cross-references the FindingProduced.id that drove this strategy.
    """

    event_type: ClassVar[str] = "StrategyExecuted"
    strategy: str = ""
    finding_id: str = ""
    text_after_size: int = 0


@dataclass(frozen=True)
class DecisionEmitted(LifecycleEventBase):
    """The canonical decision_id field is referenced by RefusalProduced.decision_id."""

    event_type: ClassVar[str] = "DecisionEmitted"
    action: str = "pass"
    max_risk: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "LOW"
    decision_id: str = ""
    bypass_reason: str | None = None


@dataclass(frozen=True)
class RefusalProduced(LifecycleEventBase):
    event_type: ClassVar[str] = "RefusalProduced"
    refusal_code: str = ""
    human_message_chars: int = 0
    decision_id: str = ""


@dataclass(frozen=True)
class BackendCalled(LifecycleEventBase):
    event_type: ClassVar[str] = "BackendCalled"
    backend: Literal["echo", "ollama", "openai"] = "echo"
    url: str = ""
    payload_msg_count: int = 0


@dataclass(frozen=True)
class BackendResponded(LifecycleEventBase):
    event_type: ClassVar[str] = "BackendResponded"
    duration_ms: float = 0.0
    http_status: int = 200
    response_msg_chars: int = 0
    response_finish_reason: str | None = None
    swap_origin_id: str | None = None
    # Populated only when the configured PayloadCapturePolicy permits
    # sanitized capture (off by default). Carries the assistant's reply
    # text — note this is the LLM output, not the inbound user text.
    response_text: str | None = None


@dataclass(frozen=True)
class PayloadRewritten(LifecycleEventBase):
    event_type: ClassVar[str] = "PayloadRewritten"
    message_index: int = 0
    field: str = "content"
    before_size: int = 0
    after_size: int = 0


@dataclass(frozen=True)
class ResponseAssembled(LifecycleEventBase):
    event_type: ClassVar[str] = "ResponseAssembled"
    response_id: str = ""
    finish_reason: str = "stop"
    arc_guard_blocked: bool = False


@dataclass(frozen=True)
class RequestCompleted(LifecycleEventBase):
    """Terminator event for one rid."""

    event_type: ClassVar[str] = "RequestCompleted"
    blocked: bool = False
    pre_action: str = "pass"
    post_action: str | None = None
    total_duration_ms: float = 0.0


@dataclass(frozen=True)
class ReportFlushed(LifecycleEventBase):
    """Fires asynchronously after RequestCompleted; may arrive at the sink AFTER the terminator."""

    event_type: ClassVar[str] = "ReportFlushed"
    reporters: list[str] = field(default_factory=list)
    fanout_count: int = 0
    failure_count: int = 0


# ---------------------------------------------------------------------------
# Conditional events (5)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PolicyRuleEvaluated(LifecycleEventBase):
    """One per rule evaluated by the policy router (conditional)."""

    event_type: ClassVar[str] = "PolicyRuleEvaluated"
    rule_id: str = ""
    outcome: Literal["matched", "not_matched", "not_applicable"] = "not_applicable"
    contributed_to_action: bool = False


@dataclass(frozen=True)
class InspectorFailed(LifecycleEventBase):
    """Fires only on uncaught inspector exception. Pipeline still fail-opens."""

    event_type: ClassVar[str] = "InspectorFailed"
    inspector_name: str = ""
    exception_class: str = ""
    traceback_id: str = ""


@dataclass(frozen=True)
class PlaceholderMapBuilt(LifecycleEventBase):
    """Request-level aggregate summary (conditional).

    Distinct from per-placeholder SanitizationApplied. The `map` field is the
    most security-sensitive in the v1 taxonomy; defaults to None.
    """

    event_type: ClassVar[str] = "PlaceholderMapBuilt"
    placeholder_count: int = 0
    entity_types: list[str] = field(default_factory=list)
    map: dict[str, str] | None = None


@dataclass(frozen=True)
class RehydrationVerified(LifecycleEventBase):
    """Fires only when a real RehydrationVerifier is wired (default no-op produces no event)."""

    event_type: ClassVar[str] = "RehydrationVerified"
    verifier_id: str = ""
    outcome: Literal["verified", "rejected", "partial"] = "verified"
    rejection_reason: str | None = None


@dataclass(frozen=True)
class InspectorMatchExplain(LifecycleEventBase):
    """Fires only by inspectors that surface match metadata.

    Example: regex-based InjectionInspector populates this via its
    explain_matches() helper.
    """

    event_type: ClassVar[str] = "InspectorMatchExplain"
    inspector: str = ""
    pattern_id: str = ""
    matched_span: tuple[int, int] = (0, 0)
    explanation: str | None = None


# ---------------------------------------------------------------------------
# Tagged union
# ---------------------------------------------------------------------------


LifecycleEvent = (
    RequestStarted
    | PreProcessStarted
    | PostProcessStarted
    | PreProcessCompleted
    | PostProcessCompleted
    | StageRan
    | IntentCaptured
    | InspectorRan
    | FindingProduced
    | JailbreakDetected
    | DeceptionScored
    | FidelityScored
    | SanitizationApplied
    | PolicyResolved
    | StrategyExecuted
    | DecisionEmitted
    | RefusalProduced
    | BackendCalled
    | BackendResponded
    | PayloadRewritten
    | ResponseAssembled
    | RequestCompleted
    | ReportFlushed
    | PolicyRuleEvaluated
    | InspectorFailed
    | PlaceholderMapBuilt
    | RehydrationVerified
    | InspectorMatchExplain
)


_BASE_EVENT_TYPES: tuple[type[LifecycleEventBase], ...] = (
    RequestStarted,
    PreProcessStarted,
    PostProcessStarted,
    PreProcessCompleted,
    PostProcessCompleted,
    StageRan,
    IntentCaptured,
    InspectorRan,
    FindingProduced,
    JailbreakDetected,
    DeceptionScored,
    FidelityScored,
    SanitizationApplied,
    PolicyResolved,
    StrategyExecuted,
    DecisionEmitted,
    RefusalProduced,
    BackendCalled,
    BackendResponded,
    PayloadRewritten,
    ResponseAssembled,
    RequestCompleted,
    ReportFlushed,
)


_CONDITIONAL_EVENT_TYPES: tuple[type[LifecycleEventBase], ...] = (
    PolicyRuleEvaluated,
    InspectorFailed,
    PlaceholderMapBuilt,
    RehydrationVerified,
    InspectorMatchExplain,
)


ALL_EVENT_TYPES: tuple[type[LifecycleEventBase], ...] = (
    _BASE_EVENT_TYPES + _CONDITIONAL_EVENT_TYPES
)


__all__ = [
    "LifecycleEventBase",
    "LifecycleEvent",
    "ALL_EVENT_TYPES",
    "RequestStarted",
    "PreProcessStarted",
    "PostProcessStarted",
    "PreProcessCompleted",
    "PostProcessCompleted",
    "StageRan",
    "IntentCaptured",
    "InspectorRan",
    "FindingProduced",
    "JailbreakDetected",
    "DeceptionScored",
    "FidelityScored",
    "SanitizationApplied",
    "PolicyResolved",
    "StrategyExecuted",
    "DecisionEmitted",
    "RefusalProduced",
    "BackendCalled",
    "BackendResponded",
    "PayloadRewritten",
    "ResponseAssembled",
    "RequestCompleted",
    "ReportFlushed",
    "PolicyRuleEvaluated",
    "InspectorFailed",
    "PlaceholderMapBuilt",
    "RehydrationVerified",
    "InspectorMatchExplain",
]
