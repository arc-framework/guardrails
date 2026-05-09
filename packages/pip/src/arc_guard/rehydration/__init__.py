"""Rehydration sub-package: verifier defaults + apply helpers."""

from __future__ import annotations

from arc_guard.rehydration.apply import (
    GUARD_REHYDRATION_APPLIED_EVENT,
    GUARD_REHYDRATION_REJECTED_EVENT,
    apply_rehydration,
)
from arc_guard.rehydration.verifier import NullRehydrationVerifier

__all__ = [
    "NullRehydrationVerifier",
    "apply_rehydration",
    "GUARD_REHYDRATION_APPLIED_EVENT",
    "GUARD_REHYDRATION_REJECTED_EVENT",
]
