"""``SentenceTransformerIntentEncoder`` — wraps a sentence-transformers model.

Imports ``sentence_transformers`` and ``numpy`` lazily; the rest of
the package never imports these directly. Failures route through
``IntentEncoderError`` per the failure-mode contract.
"""

from __future__ import annotations

from typing import Any

from arc_guard_core.exceptions import IntentEncoderError
from arc_guard_core.protocols.intent_encoder import IntentRepresentation


class SentenceTransformerIntentEncoder:
    """Embedding-based encoder. ``encode(text)`` returns a numpy ndarray."""

    def __init__(
        self,
        *,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        try:
            import sentence_transformers as _st_pkg
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise IntentEncoderError(
                f"sentence-transformers not installed: {exc}",
                code="intent_encoder.model_load_failed",
                cause=exc,
            ) from exc
        try:
            self._model = SentenceTransformer(model_name)
        except Exception as exc:  # pragma: no cover — model-load failure path
            raise IntentEncoderError(
                f"Failed to load model {model_name!r}: {exc}",
                code="intent_encoder.model_load_failed",
                cause=exc,
            ) from exc
        self._model_name = model_name
        self._package_version = getattr(_st_pkg, "__version__", "unknown")

    @property
    def encoder_id(self) -> str:
        return f"{self._model_name}:{self._package_version}"

    def encode(self, text: str) -> IntentRepresentation:
        if not text:
            raise IntentEncoderError(
                "encode() received an empty string",
                code="intent_encoder.inference_failed",
            )
        try:
            vector: Any = self._model.encode(text, convert_to_numpy=True)
        except Exception as exc:
            raise IntentEncoderError(
                f"Encoder inference failed: {exc}",
                code="intent_encoder.inference_failed",
                cause=exc,
            ) from exc
        return vector


__all__ = ["SentenceTransformerIntentEncoder"]
