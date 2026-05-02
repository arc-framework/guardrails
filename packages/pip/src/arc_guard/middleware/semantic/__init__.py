"""Canned semantic backend — gated by the ``arc-guard[semantic]`` extra.

Provides ``SemanticBundle`` (encoder + scorer + verifier triple) and a
``from_sentence_transformers()`` factory mirroring the *shape* of
``OtelObservability.from_otel_sdk()`` (lazy import + factory returning
a triple). The class is named ``SemanticBundle``, NOT
``SemanticObservability`` — these are pluggable Protocol implementations
(``IntentEncoder`` / ``FidelityScorer`` / ``RehydrationVerifier``), not
observability sinks.

Importing this module without the ``[semantic]`` extra installed
raises ``ImportError`` from the lazy import inside ``_load_torch()``
when the factory runs; bare ``import`` succeeds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from arc_guard_core.protocols.fidelity_scorer import FidelityScorer
from arc_guard_core.protocols.intent_encoder import IntentEncoder
from arc_guard_core.protocols.rehydration_verifier import RehydrationVerifier


@dataclass(frozen=True)
class SemanticBundle:
    """Encoder + Scorer + Verifier triple for the canned semantic backend.

    Constructed via :meth:`from_sentence_transformers`; the bundle
    exposes typed attributes that operators wire into ``GuardPipeline``:

    .. code-block:: python

       bundle = SemanticBundle.from_sentence_transformers()
       pipeline = GuardPipeline(
           intent_encoder=bundle.encoder,
           fidelity_scorer=bundle.scorer,
           rehydration_verifier=bundle.verifier,
       )
    """

    encoder: IntentEncoder
    scorer: FidelityScorer
    verifier: RehydrationVerifier

    @classmethod
    def from_sentence_transformers(
        cls,
        *,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        injection_inspector: Any | None = None,
    ) -> SemanticBundle:
        """Build the canned bundle from a sentence-transformers model.

        Lazy-imports ``sentence_transformers`` and ``numpy``; raises
        ``ImportError`` with an install hint when the ``[semantic]``
        extra is missing.

        Args:
            model_name: Hugging Face model id; defaults to a small
                CPU-friendly all-MiniLM model.
            injection_inspector: Inspector reused for the verifier's
                Check 3 (safety regression). When ``None``, the default
                ``InjectionInspector`` is constructed.
        """
        try:
            from sentence_transformers import SentenceTransformer  # noqa: F401
            import numpy  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "SemanticBundle.from_sentence_transformers() requires the "
                "[semantic] extra. Install with: pip install arc-guard[semantic]"
            ) from exc

        from arc_guard.middleware.semantic.encoder import (
            SentenceTransformerIntentEncoder,
        )
        from arc_guard.middleware.semantic.scorer import CosineFidelityScorer
        from arc_guard.middleware.semantic.verifier import (
            SemanticRehydrationVerifier,
        )

        if injection_inspector is None:
            from arc_guard.inspectors.injection import InjectionInspector

            injection_inspector = InjectionInspector()

        encoder = SentenceTransformerIntentEncoder(model_name=model_name)
        scorer = CosineFidelityScorer()
        verifier = SemanticRehydrationVerifier(
            injection_inspector=injection_inspector,
        )
        return cls(encoder=encoder, scorer=scorer, verifier=verifier)


__all__ = ["SemanticBundle"]
