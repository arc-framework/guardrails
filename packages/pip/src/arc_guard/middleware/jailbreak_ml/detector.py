"""``ClassifierJailbreakDetector`` — wraps a HuggingFace transformer classifier.

The classifier produces a binary jailbreak probability per input. The
detector maps the probability to the closest documented category via a
small heuristic (operators with category-aware classifiers override
this by implementing the ``JailbreakDetector`` Protocol directly).

Failure mode: failures wrapped in ``JailbreakDetectorError``; posture
``closed-conservative`` — a model load / inference failure produces
no signal rather than a false-positive refusal.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from arc_guard_core.deception import ConversationState
from arc_guard_core.exceptions import JailbreakDetectorError
from arc_guard_core.jailbreak import JailbreakCategory, JailbreakSignal

_LOG = logging.getLogger("arc_guard.middleware.jailbreak_ml")

# Heuristic keyword families used to refine the category when the
# classifier produces a flat "is jailbreak" score. Operators with
# category-aware classifiers should implement the Protocol directly
# rather than rely on these keywords.
_CATEGORY_KEYWORDS: dict[JailbreakCategory, tuple[re.Pattern[str], ...]] = {
    "direct_override": (
        re.compile(r"\b(?:ignore|disregard)\s+(?:previous|prior|all)\s+(?:instructions|rules)\b", re.IGNORECASE),
        re.compile(r"\b(?:reveal|show|print)\s+(?:the\s+)?system\s+prompt\b", re.IGNORECASE),
    ),
    "role_play": (
        re.compile(r"\byou\s+are\s+(?:now\s+)?(?:DAN|an?\s+(?:unrestricted|jailbroken|evil))\b", re.IGNORECASE),
        re.compile(r"\bact\s+as\b", re.IGNORECASE),
        re.compile(r"\bpretend\s+(?:to\s+be|you\s+(?:are|were))\b", re.IGNORECASE),
    ),
    "hypothetical": (
        re.compile(r"\bhypothetically\b", re.IGNORECASE),
        re.compile(r"\bjust\s+imagine\b", re.IGNORECASE),
        re.compile(r"\bfor\s+the\s+sake\s+of\s+argument\b", re.IGNORECASE),
    ),
    "policy_erosion": (
        re.compile(r"\bas\s+we\s+(?:already\s+)?(?:agreed|discussed|established)\b", re.IGNORECASE),
        re.compile(r"\bfor\s+educational\s+purposes\s+only\b", re.IGNORECASE),
        re.compile(r"\bthis\s+is\s+just\s+a\s+test\b", re.IGNORECASE),
    ),
    "indirect_injection": (
        re.compile(r"<context>[\s\S]*?</context>", re.IGNORECASE),
        re.compile(r"\[retrieved\][\s\S]*?\[/retrieved\]", re.IGNORECASE),
    ),
}


def _classify_category(text: str) -> JailbreakCategory:
    """Return the most-specific matching category, defaulting to direct_override.

    Tries each category's keyword family in priority order. First match
    wins. The default of ``direct_override`` reflects the highest-stakes
    category — operators tuning for fewer false positives can override
    by implementing the Protocol with a category-aware classifier.
    """
    for category, patterns in _CATEGORY_KEYWORDS.items():
        if any(p.search(text) for p in patterns):
            return category
    return "direct_override"


class ClassifierJailbreakDetector:
    """HuggingFace transformer-based jailbreak detector.

    The classifier produces a binary jailbreak probability; the detector
    maps it to a ``JailbreakSignal`` with the closest category and a
    placeholder evidence reference.

    Concurrency: thread-safe (the model is read-only after load).
    Failure mode: failures wrapped in ``JailbreakDetectorError``;
    posture ``closed-conservative``.
    """

    def __init__(
        self,
        *,
        model_name: str = "protectai/deberta-v3-base-prompt-injection-v2",
        device: str | None = None,
    ) -> None:
        try:
            import transformers
            import torch
        except ImportError as exc:
            raise JailbreakDetectorError(
                "transformers + torch not installed",
                code="jailbreak_detector.model_load_failed",
                cause=exc,
            ) from exc
        try:
            self._tokenizer = transformers.AutoTokenizer.from_pretrained(model_name)
            self._model = transformers.AutoModelForSequenceClassification.from_pretrained(
                model_name,
            )
            self._device = device or "cpu"
            self._model.to(self._device)
            self._model.eval()
        except Exception as exc:
            raise JailbreakDetectorError(
                f"failed to load model {model_name!r}: {exc}",
                code="jailbreak_detector.model_load_failed",
                cause=exc,
            ) from exc
        self._model_name = model_name
        self._package_version = getattr(transformers, "__version__", "unknown")
        self._torch = torch
        self._counter: int = 0

    @property
    def detector_id(self) -> str:
        return f"{self._model_name}:{self._package_version}"

    def detect(
        self,
        text: str,
        *,
        conversation_state: ConversationState | None = None,
    ) -> tuple[JailbreakSignal, ...]:
        # ``conversation_state`` is unused by this single-turn detector;
        # accepted for Protocol conformance.
        del conversation_state
        if not text:
            return ()
        try:
            confidence = self._predict(text)
        except Exception as exc:
            raise JailbreakDetectorError(
                f"classifier inference failed: {exc}",
                code="jailbreak_detector.inference_failed",
                cause=exc,
            ) from exc

        if confidence < 0.5:
            return ()  # below borderline — no signal

        category = _classify_category(text)
        self._counter += 1
        evidence_token = f"ML_{category.upper()}_{self._counter}"
        return (
            JailbreakSignal(
                category=category,
                confidence=float(confidence),
                evidence_reference=evidence_token,
                detector_id=self.detector_id,
            ),
        )

    def _predict(self, text: str) -> float:
        """Run the classifier and return the jailbreak probability."""
        inputs = self._tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        ).to(self._device)
        with self._torch.no_grad():
            outputs = self._model(**inputs)
        logits = outputs.logits[0]
        probs = self._torch.softmax(logits, dim=-1)
        # The DeBERTa prompt-injection model outputs class 1 = injection.
        # Operators with different label conventions override the
        # detector via the Protocol directly.
        if probs.shape[0] >= 2:
            jailbreak_prob = float(probs[1].item())
        else:
            jailbreak_prob = float(probs[0].item())
        return jailbreak_prob


__all__ = ["ClassifierJailbreakDetector"]
