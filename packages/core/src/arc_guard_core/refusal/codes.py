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


__all__ = ["RefusalCode"]
