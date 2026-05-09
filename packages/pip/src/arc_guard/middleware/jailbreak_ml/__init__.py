"""Canned ML jailbreak backend — gated by the ``arc-guard[jailbreak-ml]`` extra.

Provides ``JailbreakMlBundle`` (a single-detector wrapper) and a
``from_huggingface_jailbreak()`` factory mirroring the SHAPE of the
``OtelObservability.from_otel_sdk()`` and
``SemanticBundle.from_sentence_transformers()`` factories from prior
specs (lazy import + factory returning the bundle).

Importing this module without the ``[jailbreak-ml]`` extra installed
raises ``ImportError`` from the lazy import inside the factory; the
bare import path succeeds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from arc_guard_core.protocols.jailbreak_detector import JailbreakDetector


@dataclass(frozen=True)
class JailbreakMlBundle:
    """Wraps the canned ML detector for the canned semantic backend.

    Constructed via :meth:`from_huggingface_jailbreak`. Operators wire
    ``bundle.detector`` into ``GuardPipeline(jailbreak_detector=...)``.
    """

    detector: JailbreakDetector

    @classmethod
    def from_huggingface_jailbreak(
        cls,
        *,
        model_name: str = "protectai/deberta-v3-base-prompt-injection-v2",
        device: str | None = None,
    ) -> JailbreakMlBundle:
        """Build the canned bundle from a HuggingFace classifier.

        Lazy-imports ``transformers`` and ``torch``; raises
        ``ImportError`` with an install hint when the
        ``[jailbreak-ml]`` extra is missing.

        Args:
            model_name: HuggingFace model id; defaults to a
                CPU-friendly DeBERTa-base classifier trained on a
                public jailbreak / prompt-injection corpus.
            device: Torch device string (``"cpu"`` / ``"cuda"`` /
                ``"mps"``). When ``None``, defaults to CPU.
        """
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "JailbreakMlBundle.from_huggingface_jailbreak() requires the "
                "[jailbreak-ml] extra. Install with: pip install arc-guard[jailbreak-ml]"
            ) from exc

        from arc_guard.middleware.jailbreak_ml.detector import (
            ClassifierJailbreakDetector,
        )

        detector: Any = ClassifierJailbreakDetector(
            model_name=model_name,
            device=device,
        )
        return cls(detector=detector)


__all__ = ["JailbreakMlBundle"]
