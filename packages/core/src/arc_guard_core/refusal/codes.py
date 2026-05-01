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
    FIDELITY_DROP_PLACEHOLDER = "fidelity_drop_placeholder"  # reserved for Spec 005


__all__ = ["RefusalCode"]
