"""Stub semantic scorer separates a control corpus from an adversarial one.

The realistic drift test exercises the scorer at the helper level, not
through the full pipeline: the pipeline's verify stage encodes
``result.text`` against ``captured_intent``, and on the
no-findings/no-transform path those are the same string — every score is
trivially 1.0 regardless of encoder. Drift only shows up across an
intent / answer pair that genuinely differs (model output vs original
prompt). The helper-level test pairs synthesized intent / answer
representations and asserts the scorer's distribution separates the two
populations.
"""

from __future__ import annotations

import statistics

import pytest
from arc_guard_core.fidelity import FidelityScore
from arc_guard_core.observability import (
    NullLogger,
    NullMetricSink,
)
from arc_guard_core.observability_config import FidelityThresholds
from arc_guard_core.protocols.intent_encoder import (
    IntentEncoder,
    IntentRepresentation,
)

from arc_guard.fidelity.scorer import score_fidelity


class _TopicEncoder:
    @property
    def encoder_id(self) -> str:
        return "topic-stub:1"

    def encode(self, text: str) -> IntentRepresentation:
        topics: set[str] = set()
        lowered = text.lower()
        if "weather" in lowered or "rain" in lowered or "forecast" in lowered:
            topics.add("weather")
        if "tax" in lowered or "return" in lowered or "irs" in lowered:
            topics.add("tax")
        return frozenset(topics)


class _JaccardScorer:
    def compatible_with(self, encoder: IntentEncoder) -> bool:
        return encoder.encoder_id.startswith("topic-stub:")

    def score(
        self,
        intent: IntentRepresentation,
        answer: IntentRepresentation,
    ) -> FidelityScore:
        if not isinstance(intent, frozenset) or not isinstance(answer, frozenset):
            return FidelityScore.measured(0.0)
        union = intent | answer
        if not union:
            return FidelityScore.measured(1.0)
        return FidelityScore.measured(len(intent & answer) / len(union))


_CONTROL_PAIRS = [
    ("Tell me about the weather forecast", "Today's weather forecast is sunny.")
    for _ in range(30)
]
_ADVERSARIAL_PAIRS = [
    ("Tell me about the weather forecast", "Tax returns are due April 15.")
    for _ in range(30)
]


@pytest.mark.asyncio
async def test_control_median_at_least_0_2_above_adversarial_median() -> None:
    encoder = _TopicEncoder()
    scorer = _JaccardScorer()
    thresholds = FidelityThresholds()

    async def _score_pair(prompt: str, answer: str) -> float:
        intent = encoder.encode(prompt)
        ans = encoder.encode(answer)
        score = await score_fidelity(
            intent,
            ans,
            scorer=scorer,
            thresholds=thresholds,
            correlation_id="corr-1",
            decision_id="dec-1",
            logger=NullLogger(),
            metric_sink=NullMetricSink(),
        )
        assert score.value is not None
        return score.value

    control_scores = [await _score_pair(p, a) for p, a in _CONTROL_PAIRS]
    adversarial_scores = [await _score_pair(p, a) for p, a in _ADVERSARIAL_PAIRS]

    control_median = statistics.median(control_scores)
    adversarial_median = statistics.median(adversarial_scores)

    # Control: both prompt and answer mention "weather" → Jaccard 1.0.
    # Adversarial: prompt mentions "weather", answer mentions "tax" →
    # disjoint topic sets → Jaccard 0.0. Separation = 1.0, well above
    # the documented 0.2 floor.
    assert control_median >= adversarial_median + 0.2
