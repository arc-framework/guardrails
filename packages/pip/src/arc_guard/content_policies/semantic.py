"""``SemanticContentPolicy`` — embedding-based content policy.

Lazy-imports the spec-005 intent encoder. When the ``[semantic]`` extra is
not installed, registers as a no-op rather than raising — operators see a
working pipeline with a structured warning event, not a deployment failure.

Construction-time validation rejects empty exemplar sets, malformed
exemplars, and out-of-range similarity thresholds with a load-time
configuration error so misconfigurations never reach evaluate().
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from arc_guard_core.exceptions import ConfigSchemaError
from arc_guard_core.observability import Logger, NullLogger
from arc_guard_core.protocols.content_policy import ContentPolicyDecision
from arc_guard_core.refusal.codes import RefusalCode

GUARD_CONTENT_POLICY_SEMANTIC_EXTRA_MISSING_EVENT = "guard.content_policy.semantic_extra_missing"


@runtime_checkable
class _Encoder(Protocol):
    """Minimal encoder shape consumed by ``SemanticContentPolicy``.

    Wider than ``arc_guard_core.protocols.intent_encoder.IntentEncoder``
    on purpose: stub encoders used in tests don't need the
    ``encoder_id`` property. The bundled
    ``SentenceTransformerIntentEncoder`` satisfies this implicitly.
    """

    def encode(self, text: str) -> Any: ...


def _coerce_to_list(vector: Any) -> list[float]:
    """Coerce an encoder output to a Python list of floats.

    Handles numpy arrays (the bundled encoder returns ndarray) and any
    iterable of floats (test stubs). Tolerates 0-d arrays by wrapping.
    """
    tolist = getattr(vector, "tolist", None)
    result = tolist() if callable(tolist) else list(vector)
    if isinstance(result, (int, float)):
        return [float(result)]
    return [float(x) for x in result]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity in pure Python — no numpy dep at evaluate time.

    Returns 0.0 for zero-magnitude vectors instead of raising; the
    matching ``CosineFidelityScorer`` uses the same convention.
    """
    if len(a) != len(b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for av, bv in zip(a, b, strict=True):
        dot += av * bv
        norm_a += av * av
        norm_b += bv * bv
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


class SemanticContentPolicy:
    """Embedding-based content policy using the spec-005 intent encoder.

    The encoder is constructed lazily. When the ``[semantic]`` extra is
    missing, the instance flips to no-op mode (``_active=False``);
    ``evaluate()`` returns a non-matching decision and the configured
    logger receives one structured warning event.

    When the extra is installed but the encoder model artifact cannot
    load (air-gapped deployment without the model file), construction
    raises ``ConfigSchemaError`` with a message distinguishing the
    failure from the missing-extra path.

    Args:
        name: Stable name for the policy (used in events and refusal envelopes).
        exemplars: Reference texts. Each call to ``evaluate(text)``
            computes the maximum cosine similarity between ``text`` and
            any exemplar; the policy fires when that maximum is at or
            above ``similarity_threshold``.
        similarity_threshold: Float in ``[0.0, 1.0]``.
        refusal_code: ``RefusalCode`` cited on a match (default ``POLICY_BLOCK``).
        encoder: Optional pre-built encoder. When supplied, the lazy
            import path is skipped — useful for tests with stub
            encoders. The encoder must implement ``encode(text)``.
        logger: Optional structured logger. When the ``[semantic]`` extra
            is missing, the missing-extra warning is emitted via this
            logger (defaults to ``NullLogger`` so silent operation is
            still possible if the operator wants it).
    """

    def __init__(
        self,
        *,
        name: str,
        exemplars: tuple[str, ...] | list[str],
        similarity_threshold: float,
        refusal_code: RefusalCode = RefusalCode.POLICY_BLOCK,
        encoder: _Encoder | None = None,
        logger: Logger | None = None,
    ) -> None:
        if not isinstance(name, str) or not name:
            raise ConfigSchemaError(
                "SemanticContentPolicy: name must be a non-empty string",
                code="config.missing_field",
                details={"field": "name"},
            )
        exemplars_tuple: tuple[str, ...] = tuple(exemplars)
        if len(exemplars_tuple) < 1:
            raise ConfigSchemaError(
                f"SemanticContentPolicy {name!r}: zero exemplars; "
                "at least one exemplar is required",
                code="config.missing_field",
                details={"field": "exemplars", "policy_name": name},
            )
        for idx, ex in enumerate(exemplars_tuple):
            if not isinstance(ex, str) or not ex:
                raise ConfigSchemaError(
                    f"SemanticContentPolicy {name!r}: exemplar at index "
                    f"{idx} is empty or not a string",
                    code="config.type_mismatch",
                    details={
                        "field": "exemplars",
                        "policy_name": name,
                        "index": idx,
                    },
                )
        if not isinstance(similarity_threshold, (int, float)) or isinstance(
            similarity_threshold,
            bool,
        ):
            raise ConfigSchemaError(
                f"SemanticContentPolicy {name!r}: similarity_threshold must be a float",
                code="config.type_mismatch",
                details={"field": "similarity_threshold", "policy_name": name},
            )
        threshold = float(similarity_threshold)
        if not (0.0 <= threshold <= 1.0):
            raise ConfigSchemaError(
                f"SemanticContentPolicy {name!r}: similarity_threshold "
                f"{threshold!r} is outside [0.0, 1.0]",
                code="config.type_mismatch",
                details={
                    "field": "similarity_threshold",
                    "policy_name": name,
                    "value": threshold,
                },
            )

        self.name: str = name
        self.exemplars: tuple[str, ...] = exemplars_tuple
        self.similarity_threshold: float = threshold
        self.refusal_code: RefusalCode = refusal_code
        self._logger: Logger = logger or NullLogger()
        self._active: bool = False
        self._encoder: _Encoder | None = None
        self._exemplar_encodings: tuple[list[float], ...] = ()

        self._initialize_encoder(encoder)
        if self._active and self._encoder is not None:
            self._exemplar_encodings = self._encode_exemplars(self._encoder)

    def _initialize_encoder(self, encoder: _Encoder | None) -> None:
        """Wire the encoder, lazy-importing the canned backend if needed.

        Three outcomes:
          1. ``encoder`` provided -> use it directly, mark active.
          2. ``encoder=None``, ``[semantic]`` installed and model loads
             -> instantiate ``SentenceTransformerIntentEncoder``,
             mark active.
          3. ``encoder=None`` and the canned backend's ``ImportError`` fires
             -> emit warning event, leave instance inactive (no-op).
          4. ``encoder=None``, the canned backend imports but the model
             artifact fails to load -> raise ``ConfigSchemaError``
             distinguishing this case from outcome 3.
        """
        if encoder is not None:
            self._encoder = encoder
            self._active = True
            return

        try:
            from arc_guard.middleware.semantic.encoder import (
                SentenceTransformerIntentEncoder,
            )
        except ImportError:
            self._logger.event(
                GUARD_CONTENT_POLICY_SEMANTIC_EXTRA_MISSING_EVENT,
                level="warning",
                policy_name=self.name,
                install_hint="pip install arc-guard[semantic]",
            )
            self._active = False
            self._encoder = None
            return

        try:
            built_encoder: _Encoder = SentenceTransformerIntentEncoder()
        except ImportError:
            self._logger.event(
                GUARD_CONTENT_POLICY_SEMANTIC_EXTRA_MISSING_EVENT,
                level="warning",
                policy_name=self.name,
                install_hint="pip install arc-guard[semantic]",
            )
            self._active = False
            self._encoder = None
            return
        except Exception as exc:
            raise ConfigSchemaError(
                f"SemanticContentPolicy {self.name!r}: [semantic] extra is "
                f"installed but encoder model artifact is unavailable: {exc}",
                code="config.missing_field",
                details={
                    "field": "encoder_model_artifact",
                    "policy_name": self.name,
                    "cause": str(exc),
                },
                cause=exc,
            ) from exc

        self._encoder = built_encoder
        self._active = True

    def _encode_exemplars(self, encoder: _Encoder) -> tuple[list[float], ...]:
        encoded: list[list[float]] = []
        for ex in self.exemplars:
            vector = encoder.encode(ex)
            encoded.append(_coerce_to_list(vector))
        return tuple(encoded)

    def evaluate(self, text: str) -> ContentPolicyDecision:
        """Return whether ``text`` matches this policy.

        When the policy is in no-op mode (missing ``[semantic]`` extra),
        always returns a non-matching decision regardless of input.
        """
        if not self._active or self._encoder is None:
            return ContentPolicyDecision(matched=False, policy_name=self.name)

        text_vector = _coerce_to_list(self._encoder.encode(text))
        max_sim = 0.0
        for exemplar_vec in self._exemplar_encodings:
            sim = _cosine(text_vector, exemplar_vec)
            if sim > max_sim:
                max_sim = sim

        matched = max_sim >= self.similarity_threshold
        return ContentPolicyDecision(
            matched=matched,
            confidence=max_sim,
            policy_name=self.name,
            refusal_code=self.refusal_code if matched else None,
        )


__all__ = [
    "SemanticContentPolicy",
    "GUARD_CONTENT_POLICY_SEMANTIC_EXTRA_MISSING_EVENT",
]
