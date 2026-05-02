"""Typed exception hierarchy for arc-guard-core.

Every leaf exception declares its failure mode (``open``, ``closed``, or
``closed-conservative``) and the set of valid ``code`` strings it may carry.
The contract test suite under ``tests/contract/test_failure_modes.py`` asserts
these invariants.

See ``specs/002-rewrite-foundation/contracts/exceptions.university`` for the canonical
table of stages and their failure modes.

Per-leaf observability metadata (failure_class label, severity, refusal_code)
lives in ``arc_guard_core.failure_modes.FAIL_RULE``. The runtime helper
``failure_modes.lookup_rule(exc_type)`` walks the MRO and reads ``posture``
from each class's ``__failure_mode__`` ClassVar so the foundation
declaration remains the single source of truth. The mapping (read the
``FAIL_RULE`` table for the authoritative version):

- ``ApiBoundaryValidationError`` → api_validation / warn / API_INVALID_REQUEST
- ``PipelineContractValidationError`` → pipeline_contract / error /
  INTERNAL_PIPELINE_ERROR
- ``AdapterBoundaryValidationError`` → adapter_validation / error /
  INTERNAL_ADAPTER_ERROR
- ``ConfigSchemaError`` → config / critical / N/A (construction-time)
- ``ConfigCrossFieldError`` → config / critical / N/A (construction-time)
- ``InspectorError`` → inspector / warn / N/A (fail-open)
- ``StrategyError`` → strategy / error / STRATEGY_FAILED
- ``PolicyRouterError`` → policy_router / error / POLICY_BLOCK
- ``RefusalEnvelopeError`` → refusal_envelope / critical /
  INTERNAL_REFUSAL_BUILD_ERROR
- ``ReporterError`` → reporter / warn / N/A (fail-open)
- ``FlagProviderError`` → flag_provider / warn / N/A (closed-conservative)
- ``EntityProviderError`` → entity_provider / error /
  INTERNAL_ENTITY_PROVIDER_ERROR
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar, Literal

FailureMode = Literal["open", "closed", "closed-conservative"]


class ArcGuardError(Exception):
    """Base exception. Never raised directly."""

    def __init__(
            self,
            message: str,
            *,
            code: str,
            details: Mapping[str, Any] | None = None,
            cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        valid_codes: frozenset[str] = getattr(type(self), "__valid_codes__", frozenset())
        if valid_codes and code not in valid_codes:
            raise ValueError(
                f"{type(self).__name__}: code {code!r} not in __valid_codes__"
            )
        self.code = code
        self.details: Mapping[str, Any] = dict(details) if details else {}
        if cause is not None:
            self.__cause__ = cause


# ---------------------------------------------------------------------------
# Second-level groups (never raised directly)
# ---------------------------------------------------------------------------


class ConfigError(ArcGuardError):
    """Configuration load and validation failures."""


class ValidationError(ArcGuardError):
    """Boundary validation failures (config, API, pipeline contract, adapter)."""


class PipelineError(ArcGuardError):
    """Runtime pipeline failures."""


class AdapterError(ArcGuardError):
    """Provider integration failures."""


class RefusalEnvelopeError(ArcGuardError):
    """Errors raised while constructing or serializing a RefusalEnvelope."""

    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset({
        "refusal.build_failed",
        "refusal.unknown_code",
    })


# ---------------------------------------------------------------------------
# Configuration leaves
# ---------------------------------------------------------------------------


class ConfigSchemaError(ConfigError):
    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset({
        "config.missing_field",
        "config.unknown_field",
        "config.type_mismatch",
    })


class ConfigCrossFieldError(ConfigError):
    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset({
        "config.cross_field_violation",
        "config.unknown_inspector",
    })


# ---------------------------------------------------------------------------
# Validation leaves
# ---------------------------------------------------------------------------


class ApiBoundaryValidationError(ValidationError):
    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset({
        "api.malformed_payload",
        "api.missing_field",
        "api.type_mismatch",
        "api.unknown_field",
    })


class PipelineContractValidationError(ValidationError):
    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset({
        "pipeline.invalid_span",
        "pipeline.invalid_score",
        "pipeline.invalid_severity",
        "pipeline.missing_inspector",
        "pipeline.invalid_decision",
    })


class AdapterBoundaryValidationError(ValidationError):
    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset({
        "adapter.invalid_input",
        "adapter.invalid_output",
    })


# ---------------------------------------------------------------------------
# Pipeline leaves
# ---------------------------------------------------------------------------


class InspectorError(PipelineError):
    __failure_mode__: ClassVar[FailureMode] = "open"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset({
        "inspector.timeout",
        "inspector.malformed_finding",
        "inspector.unhandled",
    })


class StrategyError(PipelineError):
    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset({
        "strategy.failed",
        "strategy.unsupported_action",
    })


class PolicyRouterError(PipelineError):
    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset({
        "router.no_decision",
        "router.conflicting_decisions",
    })


# ---------------------------------------------------------------------------
# Adapter leaves
# ---------------------------------------------------------------------------


class ReporterError(AdapterError):
    __failure_mode__: ClassVar[FailureMode] = "open"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset({
        "reporter.queue_full",
        "reporter.publish_failed",
        "reporter.unhandled",
    })


class FlagProviderError(AdapterError):
    __failure_mode__: ClassVar[FailureMode] = "closed-conservative"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset({
        "flag.lookup_failed",
        "flag.unhandled",
    })


class EntityProviderError(AdapterError):
    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset({
        "entity.load_failed",
        "entity.duplicate_name",
    })


__all__ = [
    "ArcGuardError",
    "ConfigError",
    "ValidationError",
    "PipelineError",
    "AdapterError",
    "RefusalEnvelopeError",
    "ConfigSchemaError",
    "ConfigCrossFieldError",
    "ApiBoundaryValidationError",
    "PipelineContractValidationError",
    "AdapterBoundaryValidationError",
    "InspectorError",
    "StrategyError",
    "PolicyRouterError",
    "ReporterError",
    "FlagProviderError",
    "EntityProviderError",
    "FailureMode",
]
