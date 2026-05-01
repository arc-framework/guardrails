"""arc-guard-core — zero-dep contract layer for arc-guardrails.

The names exported here ARE the public surface, snapshotted by the contract
test suite under ``tests/contract/``. Adding a new public symbol requires a
CHANGELOG entry; renaming or removing one requires the deprecation flow.

See ``specs/002-rewrite-foundation/contracts/public-types.university`` and
``specs/003-sanitization-policy-core/contracts/public-types.university``.
"""

from __future__ import annotations

from arc_guard_core.config import GuardConfig
from arc_guard_core.decision import DecisionRecord, FindingSummary
from arc_guard_core.exceptions import (
    AdapterBoundaryValidationError,
    AdapterError,
    ApiBoundaryValidationError,
    ArcGuardError,
    ConfigCrossFieldError,
    ConfigError,
    ConfigSchemaError,
    EntityProviderError,
    FailureMode,
    FlagProviderError,
    InspectorError,
    PipelineContractValidationError,
    PipelineError,
    PolicyRouterError,
    RefusalEnvelopeError,
    ReporterError,
    StrategyError,
    ValidationError,
)
from arc_guard_core.observability import (
    Logger,
    MetricSink,
    NullLogger,
    NullMetricSink,
    NullTracer,
    Tracer,
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
    EntityProvider,
    FlagProvider,
    Guard,
    Inspector,
    Middleware,
    PolicyRouter,
    Reporter,
)
from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.refusal.templates import (
    DEFAULT_REFUSAL_TEMPLATES,
    RefusalTemplate,
    get_refusal_template,
    register_refusal_template,
)
from arc_guard_core.registry import EntityRegistry, register_entity
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

__version__ = "0.2.0"

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
    # policy (Spec 003)
    "RiskBand",
    "RiskThresholds",
    "PolicyRule",
    "PolicyRuleSet",
    "RoutedOutcome",
    "TransformSummary",
    # decision (Spec 003)
    "DecisionRecord",
    "FindingSummary",
    # placeholders (Spec 003)
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
    "FailureMode",
]
