"""Registered refusal codes used by ``RefusalEnvelope.code``."""

from __future__ import annotations

from enum import StrEnum


class RefusalCode(StrEnum):
    """Stable, machine-readable refusal codes.

    New codes are added in the same change that introduces them, with a
    CHANGELOG entry. Removed codes follow the deprecation flow.
    """

    JAILBREAK = "jailbreak"
    PII_CRITICAL = "pii_critical"
    STRATEGY_FAILED = "strategy_failed"
    POLICY_BLOCK = "policy_block"
    # Reserved placeholder for fidelity-drop refusals; the matching detector
    # is not implemented yet and the registered template is a stub.
    FIDELITY_DROP_PLACEHOLDER = "fidelity_drop_placeholder"
    API_INVALID_REQUEST = "api_invalid_request"
    INTERNAL_PIPELINE_ERROR = "internal_pipeline_error"
    INTERNAL_ADAPTER_ERROR = "internal_adapter_error"
    INTERNAL_REFUSAL_BUILD_ERROR = "internal_refusal_build_error"
    INTERNAL_ENTITY_PROVIDER_ERROR = "internal_entity_provider_error"
    INTERNAL_UNKNOWN_ERROR = "internal_unknown_error"


__all__ = ["RefusalCode"]
