"""Fidelity sub-package: scorer defaults + threshold-ladder helpers."""

from __future__ import annotations

from arc_guard.fidelity.scorer import (
    GUARD_FIDELITY_SCORED_EVENT,
    NullFidelityScorer,
    score_fidelity,
)

__all__ = [
    "NullFidelityScorer",
    "score_fidelity",
    "GUARD_FIDELITY_SCORED_EVENT",
]
