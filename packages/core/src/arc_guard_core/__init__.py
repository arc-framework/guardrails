"""arc-guard-core — zero-dep contract layer for arc-guardrails.

The names exported here ARE the public surface, snapshotted by the contract
test suite under ``tests/contract/``. Adding a new public symbol requires a
CHANGELOG entry; renaming or removing one requires the deprecation flow.

See ``specs/002-rewrite-foundation/contracts/public-types.university`` and
``specs/003-sanitization-policy-core/contracts/public-types.university``.
"""

from __future__ import annotations

from arc_guard_core.config import GuardConfig
from arc_guard_core.deception import (
    NOT_MEASURED as DECEPTION_NOT_MEASURED,
)
from arc_guard_core.deception import (
    ConversationState,
    DeceptionScore,
)
from arc_guard_core.decision import DecisionRecord, FindingSummary
from arc_guard_core.evaluation import (
    Configuration,
    ConfigurationMetrics,
    CorpusCategory,
    CorpusEntry,
    EvaluationReport,
    ExpectedOutcome,
)
from arc_guard_core.exceptions import (
    AdapterBoundaryValidationError,
    AdapterError,
    ApiBoundaryValidationError,
    ArcGuardError,
    ConfigCrossFieldError,
    ConfigError,
    ConfigSchemaError,
    ConversationTurnInspectorError,
    CorpusValidationError,
    EntityProviderError,
    EvaluationHarnessError,
    FailureMode,
    FidelityScorerError,
    FlagProviderError,
    InspectorError,
    IntentEncoderError,
    JailbreakDetectorError,
    PipelineContractValidationError,
    PipelineError,
    PolicyRouterError,
    RefusalEnvelopeError,
    RehydrationVerifierError,
    ReporterError,
    StrategyError,
    TransportError,
    ValidationError,
)
from arc_guard_core.failure_modes import (
    FAIL_RULE,
    FAILURE_ADAPTER_VALIDATION,
    FAILURE_API_TRANSPORT,
    FAILURE_API_VALIDATION,
    FAILURE_CONFIG,
    FAILURE_CONVERSATION_TURN_INSPECTOR,
    FAILURE_CORPUS_VALIDATION,
    FAILURE_ENTITY_PROVIDER,
    FAILURE_EVALUATION_HARNESS,
    FAILURE_FIDELITY_SCORER,
    FAILURE_FLAG_PROVIDER,
    FAILURE_INSPECTOR,
    FAILURE_INTENT_ENCODER,
    FAILURE_JAILBREAK_DETECTOR,
    FAILURE_PIPELINE_CONTRACT,
    FAILURE_POLICY_ROUTER,
    FAILURE_REFUSAL_ENVELOPE,
    FAILURE_REHYDRATION_VERIFIER,
    FAILURE_REPORTER,
    FAILURE_STRATEGY,
    FAILURE_UNKNOWN,
    UNKNOWN_POSTURE,
    UNKNOWN_RULE,
    FailureRule,
    Severity,
    lookup_rule,
)
from arc_guard_core.fidelity import NOT_MEASURED, FidelityScore
from arc_guard_core.intent_lock import IntentLock
from arc_guard_core.jailbreak import JailbreakCategory, JailbreakSignal
from arc_guard_core.observability import (
    Logger,
    MetricSink,
    NullLogger,
    NullMetricSink,
    NullTracer,
    Tracer,
)
from arc_guard_core.observability_config import (
    DeceptionThresholds,
    FidelityThresholds,
    JailbreakThresholds,
    LogLevelFloor,
    ObservabilityConfig,
)
from arc_guard_core.pipeline import GuardPipeline
from arc_guard_core.placeholders import (
    DEFAULT_PLACEHOLDERS,
    format_placeholder,
    get_placeholder,
    register_placeholder,
)
from arc_guard_core.policy import (
    PolicyRule,
    PolicyRuleSet,
    RiskBand,
    RiskThresholds,
    RoutedOutcome,
    TransformSummary,
)
from arc_guard_core.protocols import (
    ActionStrategy,
    ContentPolicy,
    ContentPolicyDecision,
    ConversationTurnInspector,
    EntityProvider,
    EvaluationHarness,
    FidelityScorer,
    FlagProvider,
    Guard,
    Inspector,
    IntentEncoder,
    IntentRepresentation,
    JailbreakDetector,
    Middleware,
    PolicyRouter,
    RehydrationDecision,
    RehydrationVerdict,
    RehydrationVerifier,
    Reporter,
    StrategySelector,
)
from arc_guard_core.protocols.attribute_redactor import (
    AttributeRedactor,
    RedactionResult,
)
from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.refusal.templates import (
    DEFAULT_REFUSAL_TEMPLATES,
    RefusalTemplate,
    get_refusal_template,
    register_refusal_template,
)
from arc_guard_core.registry import EntityRegistry, register_entity
from arc_guard_core.stages import (
    STAGE_CLASSIFY,
    STAGE_DECEPTION_INSPECT,
    STAGE_DECISION_EMIT,
    STAGE_DEFEND,
    STAGE_DESCRIPTORS,
    STAGE_EXECUTE,
    STAGE_REFUSAL,
    STAGE_REHYDRATE,
    STAGE_REPORT,
    STAGE_ROUTE,
    STAGE_SANITIZE,
    STAGE_VALIDATE,
    STAGE_VERIFY,
)
from arc_guard_core.types import (
    ClarificationRequest,
    EntityDefinition,
    Finding,
    GuardContext,
    GuardInput,
    GuardResult,
    PolicyDecision,
    RefusalEnvelope,
    RiskLevel,
)

__version__ = "0.7.0"

__all__ = [
    # version
    "__version__",
    # types
    "RiskLevel",
    "GuardContext",
    "GuardInput",
    "Finding",
    "PolicyDecision",
    "RefusalEnvelope",
    "ClarificationRequest",
    "GuardResult",
    "EntityDefinition",
    # config
    "GuardConfig",
    # pipeline
    "GuardPipeline",
    # registry
    "EntityRegistry",
    "register_entity",
    # refusal
    "RefusalCode",
    "RefusalTemplate",
    "DEFAULT_REFUSAL_TEMPLATES",
    "register_refusal_template",
    "get_refusal_template",
    # policy
    "RiskBand",
    "RiskThresholds",
    "PolicyRule",
    "PolicyRuleSet",
    "RoutedOutcome",
    "TransformSummary",
    # decision
    "DecisionRecord",
    "FindingSummary",
    # placeholders
    "DEFAULT_PLACEHOLDERS",
    "register_placeholder",
    "get_placeholder",
    "format_placeholder",
    # protocols
    "Guard",
    "Inspector",
    "ActionStrategy",
    "Reporter",
    "FlagProvider",
    "Middleware",
    "EntityProvider",
    "PolicyRouter",
    "IntentEncoder",
    "IntentRepresentation",
    "FidelityScorer",
    "RehydrationVerifier",
    "RehydrationVerdict",
    "RehydrationDecision",
    "JailbreakDetector",
    "ConversationTurnInspector",
    "EvaluationHarness",
    "StrategySelector",
    "ContentPolicy",
    "ContentPolicyDecision",
    # observability hooks
    "Tracer",
    "Logger",
    "MetricSink",
    "NullTracer",
    "NullLogger",
    "NullMetricSink",
    # exceptions
    "ArcGuardError",
    "ConfigError",
    "ConfigSchemaError",
    "ConfigCrossFieldError",
    "ValidationError",
    "ApiBoundaryValidationError",
    "PipelineContractValidationError",
    "AdapterBoundaryValidationError",
    "PipelineError",
    "InspectorError",
    "StrategyError",
    "PolicyRouterError",
    "AdapterError",
    "ReporterError",
    "FlagProviderError",
    "EntityProviderError",
    "RefusalEnvelopeError",
    "IntentEncoderError",
    "FidelityScorerError",
    "RehydrationVerifierError",
    "JailbreakDetectorError",
    "ConversationTurnInspectorError",
    "EvaluationHarnessError",
    "CorpusValidationError",
    "TransportError",
    "FailureMode",
    # fidelity types
    "FidelityScore",
    "NOT_MEASURED",
    "FidelityThresholds",
    "IntentLock",
    # jailbreak types
    "JailbreakSignal",
    "JailbreakCategory",
    "JailbreakThresholds",
    # deception types
    "DeceptionScore",
    "DECEPTION_NOT_MEASURED",
    "ConversationState",
    "DeceptionThresholds",
    # evaluation types
    "Configuration",
    "ExpectedOutcome",
    "CorpusCategory",
    "CorpusEntry",
    "ConfigurationMetrics",
    "EvaluationReport",
    # observability config
    "ObservabilityConfig",
    "LogLevelFloor",
    # failure-mode contract
    "FailureRule",
    "Severity",
    "FAIL_RULE",
    "UNKNOWN_RULE",
    "UNKNOWN_POSTURE",
    "lookup_rule",
    "FAILURE_API_VALIDATION",
    "FAILURE_PIPELINE_CONTRACT",
    "FAILURE_ADAPTER_VALIDATION",
    "FAILURE_CONFIG",
    "FAILURE_INSPECTOR",
    "FAILURE_STRATEGY",
    "FAILURE_POLICY_ROUTER",
    "FAILURE_REFUSAL_ENVELOPE",
    "FAILURE_REPORTER",
    "FAILURE_FLAG_PROVIDER",
    "FAILURE_ENTITY_PROVIDER",
    "FAILURE_INTENT_ENCODER",
    "FAILURE_FIDELITY_SCORER",
    "FAILURE_REHYDRATION_VERIFIER",
    "FAILURE_JAILBREAK_DETECTOR",
    "FAILURE_CONVERSATION_TURN_INSPECTOR",
    "FAILURE_EVALUATION_HARNESS",
    "FAILURE_CORPUS_VALIDATION",
    "FAILURE_API_TRANSPORT",
    "FAILURE_UNKNOWN",
    # attribute redaction
    "AttributeRedactor",
    "RedactionResult",
    # stages
    "STAGE_VALIDATE",
    "STAGE_DEFEND",
    "STAGE_CLASSIFY",
    "STAGE_DECEPTION_INSPECT",
    "STAGE_SANITIZE",
    "STAGE_ROUTE",
    "STAGE_EXECUTE",
    "STAGE_REFUSAL",
    "STAGE_VERIFY",
    "STAGE_REHYDRATE",
    "STAGE_DECISION_EMIT",
    "STAGE_REPORT",
    "STAGE_DESCRIPTORS",
]
