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
            raise ValueError(f"{type(self).__name__}: code {code!r} not in __valid_codes__")
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
    __valid_codes__: ClassVar[frozenset[str]] = frozenset(
        {
            "refusal.build_failed",
            "refusal.unknown_code",
        }
    )


# ---------------------------------------------------------------------------
# Configuration leaves
# ---------------------------------------------------------------------------


class ConfigSchemaError(ConfigError):
    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset(
        {
            "config.missing_field",
            "config.unknown_field",
            "config.type_mismatch",
        }
    )


class ConfigCrossFieldError(ConfigError):
    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset(
        {
            "config.cross_field_violation",
            "config.unknown_inspector",
        }
    )


class RegistryFrozenError(ConfigCrossFieldError):
    """Raised when ``register(...)`` is called after the registry was frozen.

    Subclasses ``ConfigCrossFieldError`` so the failure-mode lookup walks
    the MRO and inherits the ``config`` rule (closed posture, critical
    severity) without a separate ``FAIL_RULE`` entry.
    """

    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset(
        {
            "registry.frozen",
        }
    )


# ---------------------------------------------------------------------------
# Validation leaves
# ---------------------------------------------------------------------------


class ApiBoundaryValidationError(ValidationError):
    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset(
        {
            "api.malformed_payload",
            "api.missing_field",
            "api.type_mismatch",
            "api.unknown_field",
        }
    )


class PipelineContractValidationError(ValidationError):
    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset(
        {
            "pipeline.invalid_span",
            "pipeline.invalid_score",
            "pipeline.invalid_severity",
            "pipeline.missing_inspector",
            "pipeline.invalid_decision",
        }
    )


class AdapterBoundaryValidationError(ValidationError):
    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset(
        {
            "adapter.invalid_input",
            "adapter.invalid_output",
        }
    )


# ---------------------------------------------------------------------------
# Pipeline leaves
# ---------------------------------------------------------------------------


class InspectorError(PipelineError):
    __failure_mode__: ClassVar[FailureMode] = "open"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset(
        {
            "inspector.timeout",
            "inspector.malformed_finding",
            "inspector.unhandled",
        }
    )


class StrategyError(PipelineError):
    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset(
        {
            "strategy.failed",
            "strategy.unsupported_action",
        }
    )


class PolicyRouterError(PipelineError):
    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset(
        {
            "router.no_decision",
            "router.conflicting_decisions",
        }
    )


# ---------------------------------------------------------------------------
# Adapter leaves
# ---------------------------------------------------------------------------


class ReporterError(AdapterError):
    __failure_mode__: ClassVar[FailureMode] = "open"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset(
        {
            "reporter.queue_full",
            "reporter.publish_failed",
            "reporter.unhandled",
        }
    )


class FlagProviderError(AdapterError):
    __failure_mode__: ClassVar[FailureMode] = "closed-conservative"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset(
        {
            "flag.lookup_failed",
            "flag.unhandled",
        }
    )


class EntityProviderError(AdapterError):
    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset(
        {
            "entity.load_failed",
            "entity.duplicate_name",
        }
    )


# ---------------------------------------------------------------------------
# Intent fidelity & rehydration leaves
# ---------------------------------------------------------------------------


class IntentEncoderError(AdapterError):
    """Encoder failure — wraps model load, timeout, inference errors.

    Posture ``closed-conservative``: the pipeline degrades to the
    ``FidelityScore.NOT_MEASURED`` sentinel and continues; no refusal.
    """

    __failure_mode__: ClassVar[FailureMode] = "closed-conservative"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset(
        {
            "intent_encoder.timeout",
            "intent_encoder.model_load_failed",
            "intent_encoder.inference_failed",
        }
    )


class FidelityScorerError(AdapterError):
    """Scorer failure — wraps incompatible-pair and scoring errors.

    Posture ``open``: the pipeline logs + counts but does not refuse;
    the score defaults to the sentinel.
    """

    __failure_mode__: ClassVar[FailureMode] = "open"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset(
        {
            "fidelity_scorer.incompatible_pair",
            "fidelity_scorer.scoring_failed",
        }
    )


class RehydrationVerifierError(PipelineError):
    """Verifier failure — wraps the documented rejection reasons.

    Posture ``closed``: the pipeline keeps placeholders (rejects
    rehydration) and records the reason on the decision record;
    catastrophic verifier failures produce a ``FIDELITY_DROP`` refusal.
    """

    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset(
        {
            "rehydration_verifier.invented_placeholder",
            "rehydration_verifier.structural_shift",
            "rehydration_verifier.safety_regression",
            "rehydration_verifier.verifier_failed",
        }
    )


# ---------------------------------------------------------------------------
# Jailbreak / deception / evaluation leaves
# ---------------------------------------------------------------------------


class JailbreakDetectorError(AdapterError):
    """Detector failure — wraps model load, timeout, inference errors.

    Posture ``closed-conservative``: the pipeline produces no signal
    rather than a false-positive refusal; the failure is recorded as
    ``failure_class='jailbreak_detector'`` in observability.
    """

    __failure_mode__: ClassVar[FailureMode] = "closed-conservative"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset(
        {
            "jailbreak_detector.timeout",
            "jailbreak_detector.model_load_failed",
            "jailbreak_detector.inference_failed",
        }
    )


class ConversationTurnInspectorError(AdapterError):
    """Inspector failure — wraps state-validation and inference errors.

    Posture ``closed-conservative``: the pipeline emits
    ``DeceptionScore.NOT_MEASURED`` and the threshold ladder is a no-op.
    """

    __failure_mode__: ClassVar[FailureMode] = "closed-conservative"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset(
        {
            "conversation_turn_inspector.state_invalid",
            "conversation_turn_inspector.inference_failed",
        }
    )


class EvaluationHarnessError(PipelineError):
    """Harness failure — the report cannot be trusted.

    Posture ``closed``: the CLI exits non-zero and writes a
    partial-report trail for debugging.
    """

    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset(
        {
            "evaluation_harness.configuration_invalid",
            "evaluation_harness.corpus_unreadable",
            "evaluation_harness.metric_compute_failed",
        }
    )


class CorpusValidationError(ValidationError):
    """Corpus loader failure — malformed corpus must fail loud.

    Posture ``closed``: raised at load time before the harness sees
    the data.
    """

    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset(
        {
            "corpus.entry_invalid",
            "corpus.schema_mismatch",
            "corpus.empty",
        }
    )


# ---------------------------------------------------------------------------
# Transport-layer leaf
# ---------------------------------------------------------------------------


class TransportError(PipelineError):
    """Transport-layer failure — timeout, oversized payload, malformed transport state.

    Posture ``closed``: transport failures produce a structured refusal
    envelope (``RefusalCode.API_TRANSPORT_TIMEOUT`` for timeouts,
    ``API_INVALID_REQUEST`` for oversized / malformed payloads). They
    do not silently degrade.
    """

    __failure_mode__: ClassVar[FailureMode] = "closed"
    __valid_codes__: ClassVar[frozenset[str]] = frozenset(
        {
            "transport.timeout",
            "transport.payload_too_large",
            "transport.invalid_state",
        }
    )


__all__ = [
    "ArcGuardError",
    "ConfigError",
    "ValidationError",
    "PipelineError",
    "AdapterError",
    "RefusalEnvelopeError",
    "ConfigSchemaError",
    "ConfigCrossFieldError",
    "RegistryFrozenError",
    "ApiBoundaryValidationError",
    "PipelineContractValidationError",
    "AdapterBoundaryValidationError",
    "InspectorError",
    "StrategyError",
    "PolicyRouterError",
    "ReporterError",
    "FlagProviderError",
    "EntityProviderError",
    "IntentEncoderError",
    "FidelityScorerError",
    "RehydrationVerifierError",
    "JailbreakDetectorError",
    "ConversationTurnInspectorError",
    "EvaluationHarnessError",
    "CorpusValidationError",
    "TransportError",
    "FailureMode",
]
