"""``CosineFidelityScorer`` — cosine similarity over numpy embedding vectors."""

from __future__ import annotations

from typing import Any

from arc_guard_core.exceptions import FidelityScorerError
from arc_guard_core.fidelity import FidelityScore
from arc_guard_core.protocols.intent_encoder import (
    IntentEncoder,
    IntentRepresentation,
)


class CosineFidelityScorer:
    """Cosine similarity, clamped to ``[0.0, 1.0]``."""

    def compatible_with(self, encoder: IntentEncoder) -> bool:
        return encoder.encoder_id.startswith("sentence-transformers/")

    def score(
        self,
        intent: IntentRepresentation,
        answer: IntentRepresentation,
    ) -> FidelityScore:
        try:
            import numpy as np
        except ImportError as exc:  # pragma: no cover
            raise FidelityScorerError(
                "numpy not installed",
                code="fidelity_scorer.scoring_failed",
                cause=exc,
            ) from exc

        intent_vec: Any = intent
        answer_vec: Any = answer
        try:
            i = np.asarray(intent_vec, dtype=float)
            a = np.asarray(answer_vec, dtype=float)
            i_norm = np.linalg.norm(i)
            a_norm = np.linalg.norm(a)
            if i_norm == 0.0 or a_norm == 0.0:
                return FidelityScore.measured(0.0)
            cosine = float(np.dot(i, a) / (i_norm * a_norm))
        except Exception as exc:
            raise FidelityScorerError(
                f"Cosine scoring failed: {exc}",
                code="fidelity_scorer.scoring_failed",
                cause=exc,
            ) from exc
        # Cosine in [-1, 1] — map negatives to 0 so the contract's
        # [0, 1] range holds.
        clamped = max(0.0, min(1.0, cosine))
        return FidelityScore.measured(clamped)


__all__ = ["CosineFidelityScorer"]
