"""Per-request lifecycle observability surface for arc-guardrails.

Public Protocol (`LifecycleSink`), null default (`NullLifecycleSink`), the
twenty-eight typed event dataclasses (`LifecycleEvent` union), and the
ULID generator for event ids.

Concrete sinks (`RingBufferLifecycleSink`, `SqliteLifecycleSink`,
`CompositeLifecycleSink`) live in `arc_guard.observability` to keep
`arc-guard-core` provider-neutral and stdlib-only.
"""

from arc_guard_core.lifecycle._ulid import new_event_id
from arc_guard_core.lifecycle.config import (
    NullPayloadCapturePolicy,
    PayloadCapturePolicy,
)
from arc_guard_core.lifecycle.emitter import LifecycleEmitter
from arc_guard_core.lifecycle.events import (
    ALL_EVENT_TYPES,
    BackendCalled,
    BackendResponded,
    DeceptionScored,
    DecisionEmitted,
    FidelityScored,
    FindingProduced,
    InspectorFailed,
    InspectorMatchExplain,
    InspectorRan,
    IntentCaptured,
    JailbreakDetected,
    LifecycleEvent,
    LifecycleEventBase,
    PayloadRewritten,
    PlaceholderMapBuilt,
    PolicyResolved,
    PolicyRuleEvaluated,
    PostProcessCompleted,
    PostProcessStarted,
    PreProcessCompleted,
    PreProcessStarted,
    RefusalProduced,
    RehydrationVerified,
    ReportFlushed,
    RequestCompleted,
    RequestStarted,
    ResponseAssembled,
    SanitizationApplied,
    StageRan,
    StrategyExecuted,
)
from arc_guard_core.lifecycle.sink import LifecycleSink, NullLifecycleSink

__all__ = [
    # Protocol + default impl
    "LifecycleSink",
    "NullLifecycleSink",
    # Emission helper (shared across api transport + pipeline)
    "LifecycleEmitter",
    # Payload-capture policy (opt-in richer event content)
    "PayloadCapturePolicy",
    "NullPayloadCapturePolicy",
    # Universal envelope + tagged union
    "LifecycleEventBase",
    "LifecycleEvent",
    "ALL_EVENT_TYPES",
    # Helpers
    "new_event_id",
    # Base events (23)
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
    # Conditional events (5)
    "PolicyRuleEvaluated",
    "InspectorFailed",
    "PlaceholderMapBuilt",
    "RehydrationVerified",
    "InspectorMatchExplain",
]
