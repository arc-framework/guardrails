"""Registered refusal codes used by ``RefusalEnvelope.code``.

The ``FIDELITY_DROP`` member was previously reserved as
``FIDELITY_DROP_PLACEHOLDER`` (a placeholder reservation with a stub
template). It is now the live code emitted by the fidelity-drop refusal
path; the rename is recorded in the CHANGELOG.
"""

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
    FIDELITY_DROP = "fidelity_drop"
    API_INVALID_REQUEST = "api_invalid_request"
    INTERNAL_PIPELINE_ERROR = "internal_pipeline_error"
    INTERNAL_ADAPTER_ERROR = "internal_adapter_error"
    INTERNAL_REFUSAL_BUILD_ERROR = "internal_refusal_build_error"
    INTERNAL_ENTITY_PROVIDER_ERROR = "internal_entity_provider_error"
    INTERNAL_UNKNOWN_ERROR = "internal_unknown_error"


__all__ = ["RefusalCode"]
