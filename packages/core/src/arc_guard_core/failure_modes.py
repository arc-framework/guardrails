"""Failure-mode contract: per-leaf-exception observability rule table.

Posture (``open`` / ``closed`` / ``closed-conservative``) is read from each
exception class's foundation ``__failure_mode__`` ClassVar. This module
contributes the three columns the foundation does not own:

- ``failure_class`` — stable string label for observability attributes
- ``severity`` — log/event severity for the failure emission
- ``refusal_code`` — populated for ``closed`` posture entries that produce
  a refusal envelope; ``None`` for fail-open / construction-time entries

The runtime helper ``lookup_rule(exc_type)`` walks the exception's MRO,
returns the matching ``FailureRule``, and reads posture from
``cls.__failure_mode__`` so the foundation declaration remains the single
source of truth. Falls back to the ``unknown`` rule when no MRO ancestor
matches a key.
"""

from __future__ import annotations

from typing import Final, Literal, NamedTuple

from arc_guard_core.exceptions import (
    AdapterBoundaryValidationError,
    ApiBoundaryValidationError,
    ConfigCrossFieldError,
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
    PolicyRouterError,
    RefusalEnvelopeError,
    RehydrationVerifierError,
    ReporterError,
    StrategyError,
    TransportError,
)
from arc_guard_core.refusal.codes import RefusalCode

# ---------------------------------------------------------------------------
# Failure-class identifiers (string-on-the-wire labels)
# ---------------------------------------------------------------------------

FAILURE_API_VALIDATION: Final[str] = "api_validation"
FAILURE_PIPELINE_CONTRACT: Final[str] = "pipeline_contract"
FAILURE_ADAPTER_VALIDATION: Final[str] = "adapter_validation"
FAILURE_CONFIG: Final[str] = "config"
FAILURE_INSPECTOR: Final[str] = "inspector"
FAILURE_STRATEGY: Final[str] = "strategy"
FAILURE_POLICY_ROUTER: Final[str] = "policy_router"
FAILURE_REFUSAL_ENVELOPE: Final[str] = "refusal_envelope"
FAILURE_REPORTER: Final[str] = "reporter"
FAILURE_FLAG_PROVIDER: Final[str] = "flag_provider"
FAILURE_ENTITY_PROVIDER: Final[str] = "entity_provider"
FAILURE_INTENT_ENCODER: Final[str] = "intent_encoder"
FAILURE_FIDELITY_SCORER: Final[str] = "fidelity_scorer"
FAILURE_REHYDRATION_VERIFIER: Final[str] = "rehydration_verifier"
FAILURE_JAILBREAK_DETECTOR: Final[str] = "jailbreak_detector"
FAILURE_CONVERSATION_TURN_INSPECTOR: Final[str] = "conversation_turn_inspector"
FAILURE_EVALUATION_HARNESS: Final[str] = "evaluation_harness"
FAILURE_CORPUS_VALIDATION: Final[str] = "corpus_validation"
FAILURE_API_TRANSPORT: Final[str] = "api_transport"
FAILURE_UNKNOWN: Final[str] = "unknown"


Severity = Literal["info", "warn", "error", "critical"]


class FailureRule(NamedTuple):
    """Per-exception observability metadata.

    Posture is *not* in this tuple — it is read from
    ``cls.__failure_mode__`` at lookup time so the foundation declaration
    is the single source of truth. ``refusal_code`` is ``None`` for
    fail-open and construction-time entries that do not produce a
    refusal envelope.
    """

    failure_class: str
    severity: Severity
    refusal_code: RefusalCode | None


FAIL_RULE: dict[type[Exception], FailureRule] = {
    ApiBoundaryValidationError: FailureRule(
        FAILURE_API_VALIDATION, "warn", RefusalCode.API_INVALID_REQUEST,
    ),
    PipelineContractValidationError: FailureRule(
        FAILURE_PIPELINE_CONTRACT, "error", RefusalCode.INTERNAL_PIPELINE_ERROR,
    ),
    AdapterBoundaryValidationError: FailureRule(
        FAILURE_ADAPTER_VALIDATION, "error", RefusalCode.INTERNAL_ADAPTER_ERROR,
    ),
    ConfigSchemaError: FailureRule(
        FAILURE_CONFIG, "critical", None,
    ),
    ConfigCrossFieldError: FailureRule(
        FAILURE_CONFIG, "critical", None,
    ),
    InspectorError: FailureRule(
        FAILURE_INSPECTOR, "warn", None,
    ),
    StrategyError: FailureRule(
        FAILURE_STRATEGY, "error", RefusalCode.STRATEGY_FAILED,
    ),
    PolicyRouterError: FailureRule(
        FAILURE_POLICY_ROUTER, "error", RefusalCode.POLICY_BLOCK,
    ),
    RefusalEnvelopeError: FailureRule(
        FAILURE_REFUSAL_ENVELOPE, "critical", RefusalCode.INTERNAL_REFUSAL_BUILD_ERROR,
    ),
    ReporterError: FailureRule(
        FAILURE_REPORTER, "warn", None,
    ),
    FlagProviderError: FailureRule(
        FAILURE_FLAG_PROVIDER, "warn", None,
    ),
    EntityProviderError: FailureRule(
        FAILURE_ENTITY_PROVIDER, "error", RefusalCode.INTERNAL_ENTITY_PROVIDER_ERROR,
    ),
    IntentEncoderError: FailureRule(
        FAILURE_INTENT_ENCODER, "warn", None,
    ),
    FidelityScorerError: FailureRule(
        FAILURE_FIDELITY_SCORER, "warn", None,
    ),
    RehydrationVerifierError: FailureRule(
        FAILURE_REHYDRATION_VERIFIER, "error", RefusalCode.FIDELITY_DROP,
    ),
    JailbreakDetectorError: FailureRule(
        FAILURE_JAILBREAK_DETECTOR, "warn", None,
    ),
    ConversationTurnInspectorError: FailureRule(
        FAILURE_CONVERSATION_TURN_INSPECTOR, "warn", None,
    ),
    EvaluationHarnessError: FailureRule(
        FAILURE_EVALUATION_HARNESS, "error", RefusalCode.INTERNAL_PIPELINE_ERROR,
    ),
    CorpusValidationError: FailureRule(
        FAILURE_CORPUS_VALIDATION, "error", RefusalCode.API_INVALID_REQUEST,
    ),
    TransportError: FailureRule(
        FAILURE_API_TRANSPORT, "error", RefusalCode.API_TRANSPORT_TIMEOUT,
    ),
}

UNKNOWN_RULE: Final[FailureRule] = FailureRule(
    FAILURE_UNKNOWN, "critical", RefusalCode.INTERNAL_UNKNOWN_ERROR,
)
UNKNOWN_POSTURE: Final[FailureMode] = "closed"


def lookup_rule(exc_type: type[BaseException]) -> tuple[FailureRule, FailureMode]:
    """Return the ``(rule, posture)`` pair for an exception type.

    Walks the type's MRO to find the first ancestor that appears as a
    ``FAIL_RULE`` key. Reads posture from ``cls.__failure_mode__`` on the
    matched ancestor. When no ancestor matches, returns the unknown rule
    with posture ``closed``.
    """
    for cls in exc_type.__mro__:
        if cls in FAIL_RULE:
            posture: FailureMode = cls.__failure_mode__  # type: ignore[attr-defined]
            return FAIL_RULE[cls], posture
    return UNKNOWN_RULE, UNKNOWN_POSTURE


__all__ = [
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
    "Severity",
    "FailureRule",
    "FAIL_RULE",
    "UNKNOWN_RULE",
    "UNKNOWN_POSTURE",
    "lookup_rule",
]
