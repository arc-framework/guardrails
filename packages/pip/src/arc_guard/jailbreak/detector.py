"""``RuleBasedJailbreakDetector`` — curated regex/keyword family across 5 categories.

Default offline-capable detector. Hits each of the documented
categories with a small set of stable patterns:

- ``role_play`` — "you are now <persona>", "act as <persona>", "DAN", "from now on you are".
- ``hypothetical`` — "hypothetically", "just imagine", "for the sake of argument", "let's pretend".
- ``policy_erosion`` — "as we agreed", "we already discussed", "for educational purposes only", "this is just a test".
- ``indirect_injection`` — injection markers inside common retrieval-context delimiters
  (``<context>...</context>``, ``[retrieved]...[/retrieved]``).
- ``direct_override`` — "ignore previous instructions", "disregard your prompt", "system prompt", "ignore all rules".

Each match produces a ``JailbreakSignal`` with a documented placeholder
``evidence_reference`` (e.g. ``DIRECT_OVERRIDE_1``) — never raw text.
Confidence scores are calibrated per the contract: 0.5 borderline, 0.7
likely, 0.9 near-certain.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from arc_guard_core.deception import ConversationState
from arc_guard_core.exceptions import JailbreakDetectorError
from arc_guard_core.jailbreak import JailbreakCategory, JailbreakSignal

GUARD_JAILBREAK_DETECTED_EVENT = "guard.jailbreak.detected"


@dataclass(frozen=True)
class _Pattern:
    category: JailbreakCategory
    regex: re.Pattern[str]
    confidence: float
    evidence_token: str  # e.g. "ROLE_PLAY", combined with an index


_PATTERNS: tuple[_Pattern, ...] = (
    # --- direct_override (most regex-catchable; high confidence) ---
    _Pattern(
        category="direct_override",
        regex=re.compile(
            r"\bignore\s+(?:all\s+)?(?:previous|prior|earlier)\s+(?:instructions|rules|directives)\b",
            re.IGNORECASE,
        ),
        confidence=0.95,
        evidence_token="DIRECT_OVERRIDE",
    ),
    _Pattern(
        category="direct_override",
        regex=re.compile(
            r"\bdisregard\s+(?:your|the|all|previous|prior)\s+(?:prompt|instructions|rules|directives)\b",
            re.IGNORECASE,
        ),
        confidence=0.95,
        evidence_token="DIRECT_OVERRIDE",
    ),
    _Pattern(
        category="direct_override",
        regex=re.compile(
            r"\b(?:reveal|show|print|output|display)\s+(?:the\s+|your\s+)?system\s+prompt\b",
            re.IGNORECASE,
        ),
        confidence=0.92,
        evidence_token="DIRECT_OVERRIDE",
    ),
    _Pattern(
        category="direct_override",
        regex=re.compile(r"\bignore\s+all\s+rules\b", re.IGNORECASE),
        confidence=0.92,
        evidence_token="DIRECT_OVERRIDE",
    ),
    # --- role_play ---
    _Pattern(
        category="role_play",
        regex=re.compile(
            r"\byou\s+are\s+(?:now\s+)?(?:DAN|an\s+unrestricted|an\s+ai\s+without|jailbroken)\b",
            re.IGNORECASE,
        ),
        confidence=0.92,
        evidence_token="ROLE_PLAY",
    ),
    _Pattern(
        category="role_play",
        regex=re.compile(
            r"\bact\s+as\s+(?:if\s+you\s+(?:were|are)\s+)?(?:an?\s+)?(?:unrestricted|jailbroken|evil|uncensored)\b",
            re.IGNORECASE,
        ),
        confidence=0.88,
        evidence_token="ROLE_PLAY",
    ),
    _Pattern(
        category="role_play",
        regex=re.compile(r"\bfrom\s+now\s+on\s+you\s+are\b", re.IGNORECASE),
        confidence=0.78,
        evidence_token="ROLE_PLAY",
    ),
    _Pattern(
        category="role_play",
        regex=re.compile(
            r"\bpretend\s+(?:to\s+be|you\s+(?:are|were))\s+(?:an?\s+)?(?:unrestricted|jailbroken|evil)\b",
            re.IGNORECASE,
        ),
        confidence=0.85,
        evidence_token="ROLE_PLAY",
    ),
    # --- hypothetical ---
    _Pattern(
        category="hypothetical",
        regex=re.compile(r"\bjust\s+hypothetically\b", re.IGNORECASE),
        confidence=0.72,
        evidence_token="HYPOTHETICAL",
    ),
    _Pattern(
        category="hypothetical",
        regex=re.compile(r"\bhypothetically\s+speaking\b", re.IGNORECASE),
        confidence=0.72,
        evidence_token="HYPOTHETICAL",
    ),
    _Pattern(
        category="hypothetical",
        regex=re.compile(r"\bfor\s+the\s+sake\s+of\s+argument\b", re.IGNORECASE),
        confidence=0.65,
        evidence_token="HYPOTHETICAL",
    ),
    _Pattern(
        category="hypothetical",
        regex=re.compile(
            r"\b(?:let'?s\s+)?(?:imagine|pretend)\s+(?:that\s+)?(?:we|you|i)\b", re.IGNORECASE
        ),
        confidence=0.6,
        evidence_token="HYPOTHETICAL",
    ),
    # --- policy_erosion ---
    _Pattern(
        category="policy_erosion",
        regex=re.compile(
            r"\bas\s+we\s+(?:already\s+)?(?:agreed|discussed|established)\b", re.IGNORECASE
        ),
        confidence=0.78,
        evidence_token="POLICY_EROSION",
    ),
    _Pattern(
        category="policy_erosion",
        regex=re.compile(r"\bfor\s+educational\s+purposes\s+(?:only|of)\b", re.IGNORECASE),
        confidence=0.7,
        evidence_token="POLICY_EROSION",
    ),
    _Pattern(
        category="policy_erosion",
        regex=re.compile(r"\bthis\s+is\s+just\s+a\s+test\b", re.IGNORECASE),
        confidence=0.65,
        evidence_token="POLICY_EROSION",
    ),
    _Pattern(
        category="policy_erosion",
        regex=re.compile(
            r"\b(?:we|you)\s+(?:already\s+)?(?:agreed|established)\s+(?:that|earlier)\b",
            re.IGNORECASE,
        ),
        confidence=0.7,
        evidence_token="POLICY_EROSION",
    ),
    # --- indirect_injection ---
    _Pattern(
        category="indirect_injection",
        regex=re.compile(
            r"<context>[\s\S]{0,200}?(?:ignore|disregard|override|new\s+instructions)[\s\S]{0,200}?</context>",
            re.IGNORECASE,
        ),
        confidence=0.85,
        evidence_token="INDIRECT_INJECTION",
    ),
    _Pattern(
        category="indirect_injection",
        regex=re.compile(
            r"\[retrieved\][\s\S]{0,200}?(?:ignore|disregard|override|new\s+instructions)[\s\S]{0,200}?\[/retrieved\]",
            re.IGNORECASE,
        ),
        confidence=0.85,
        evidence_token="INDIRECT_INJECTION",
    ),
)


class RuleBasedJailbreakDetector:
    """Default offline detector — curated regex/keyword family across 5 categories.

    Concurrency: thread-safe (compiled patterns are immutable).
    Failure mode: failures wrapped in ``JailbreakDetectorError``;
    posture ``closed-conservative`` — the pipeline produces no signal
    rather than a false-positive refusal.
    """

    @property
    def detector_id(self) -> str:
        return "rule-based:1"

    def detect(
        self,
        text: str,
        *,
        conversation_state: ConversationState | None = None,
    ) -> tuple[JailbreakSignal, ...]:
        # ``conversation_state`` is unused by the rule-based detector;
        # accepted for Protocol conformance and future stateful refinements.
        del conversation_state
        if not text:
            return ()
        try:
            return tuple(self._scan(text))
        except Exception as exc:  # pragma: no cover — defensive
            raise JailbreakDetectorError(
                f"rule-based detector raised: {exc}",
                code="jailbreak_detector.inference_failed",
                cause=exc,
            ) from exc

    def _scan(self, text: str) -> Iterable[JailbreakSignal]:
        per_category_index: dict[JailbreakCategory, int] = {
            "role_play": 0,
            "hypothetical": 0,
            "policy_erosion": 0,
            "indirect_injection": 0,
            "direct_override": 0,
        }
        # Track highest confidence per category — multiple matches in
        # the same category collapse into one signal at the highest
        # confidence so per-category P/R math stays clean.
        best_per_category: dict[JailbreakCategory, tuple[float, str]] = {}
        for pattern in _PATTERNS:
            for _ in pattern.regex.finditer(text):
                per_category_index[pattern.category] += 1
                token = f"{pattern.evidence_token}_{per_category_index[pattern.category]}"
                prior = best_per_category.get(pattern.category)
                if prior is None or pattern.confidence > prior[0]:
                    best_per_category[pattern.category] = (
                        pattern.confidence,
                        token,
                    )
        for category, (confidence, token) in best_per_category.items():
            yield JailbreakSignal(
                category=category,
                confidence=confidence,
                evidence_reference=token,
                detector_id=self.detector_id,
            )


__all__ = [
    "RuleBasedJailbreakDetector",
    "GUARD_JAILBREAK_DETECTED_EVENT",
]
