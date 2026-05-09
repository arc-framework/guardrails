"""Semantic content policy fires on paraphrased input; passes on unrelated.

Uses a deterministic stub encoder so the test does not depend on the
optional [semantic] extra. The encoder maps "forbidden" inputs to a
vector close to its single exemplar; "benign" inputs map to an
orthogonal vector. Threshold is set in [0.0, 1.0] so the assertions
exercise the cosine similarity path.

Acceptance scenario 4 (custom backend honored) is covered by the
companion test in ``test_custom_content_policy.py``.
"""

from __future__ import annotations

from typing import Any

from arc_guard.content_policies.aggregate import (
    build_aggregate_refusal_envelope,
    evaluate_content_policies,
)
from arc_guard.content_policies.registry import (
    _reset_for_testing,
    list_registered,
    register_content_policy,
)
from arc_guard.content_policies.semantic import SemanticContentPolicy


class _KeyedEncoder:
    """Maps inputs that share a tag to overlapping vectors.

    A tag is the prefix before the first ``::`` separator. Inputs with
    the same tag get the same direction (high similarity); inputs with
    different tags get orthogonal directions (low similarity).
    """

    _DIRECTIONS: dict[str, list[float]] = {
        "forbidden": [1.0, 0.0, 0.0],
        "benign": [0.0, 1.0, 0.0],
        "other": [0.0, 0.0, 1.0],
    }

    def encode(self, text: str) -> list[float]:
        tag = text.split("::", 1)[0] if "::" in text else "other"
        return list(self._DIRECTIONS.get(tag, self._DIRECTIONS["other"]))


def _setup_module() -> None:
    _reset_for_testing()


def test_paraphrase_fires_policy_and_produces_refusal_envelope() -> None:
    _setup_module()
    encoder = _KeyedEncoder()
    policy = SemanticContentPolicy(
        name="competitor_pricing",
        exemplars=("forbidden::reference exemplar",),
        similarity_threshold=0.78,
        encoder=encoder,
    )
    register_content_policy("competitor_pricing", policy)

    policies = [policy]
    firings = evaluate_content_policies(
        "forbidden::what does competitor X charge",
        policies,
    )
    assert len(firings) == 1
    assert firings[0].name == "competitor_pricing"
    assert firings[0].decision.matched is True

    envelope = build_aggregate_refusal_envelope(firings)
    assert envelope.code == "policy_block"
    assert envelope.policy == "competitor_pricing"
    assert envelope.metadata["primary_policy"] == "competitor_pricing"
    assert isinstance(envelope.metadata["firing_policies"], list)
    assert envelope.metadata["firing_policies"][0]["name"] == "competitor_pricing"


def test_unrelated_input_does_not_fire_policy() -> None:
    _setup_module()
    encoder = _KeyedEncoder()
    policy = SemanticContentPolicy(
        name="competitor_pricing",
        exemplars=("forbidden::reference exemplar",),
        similarity_threshold=0.78,
        encoder=encoder,
    )
    register_content_policy("competitor_pricing", policy)

    firings = evaluate_content_policies(
        "benign::what is the weather today",
        [policy],
    )
    assert firings == []


def test_below_threshold_does_not_fire_even_with_some_similarity() -> None:
    _setup_module()

    class _AlmostMatching:
        def encode(self, text: str) -> list[float]:
            if text == "exemplar":
                return [1.0, 0.0]
            return [0.6, 0.8]

    policy = SemanticContentPolicy(
        name="strict_topic",
        exemplars=("exemplar",),
        similarity_threshold=0.95,
        encoder=_AlmostMatching(),
    )
    register_content_policy("strict_topic", policy)

    firings = evaluate_content_policies("not exemplar", [policy])
    assert firings == []


def test_registry_stores_policy_for_pipeline_dispatch() -> None:
    _setup_module()
    encoder = _KeyedEncoder()
    policy = SemanticContentPolicy(
        name="competitor_pricing",
        exemplars=("forbidden::ref",),
        similarity_threshold=0.5,
        encoder=encoder,
    )
    register_content_policy("competitor_pricing", policy)
    assert "competitor_pricing" in list_registered()


def test_acceptance_scenario_4_custom_backend_honored() -> None:
    """Acceptance scenario 4: a custom ContentPolicy that is NOT a
    SemanticContentPolicy fires in the same lifecycle position
    (the aggregate evaluation helper) and produces an equivalent
    refusal envelope.
    """
    _setup_module()

    class _AlwaysFiringContentPolicy:
        """Custom content policy whose evaluate() always matches."""

        name = "external_classifier"

        def evaluate(self, text: str) -> Any:
            from arc_guard_core.protocols.content_policy import (
                ContentPolicyDecision,
            )
            from arc_guard_core.refusal.codes import RefusalCode

            return ContentPolicyDecision(
                matched=True,
                confidence=0.99,
                policy_name=self.name,
                refusal_code=RefusalCode.POLICY_BLOCK,
            )

    custom = _AlwaysFiringContentPolicy()
    register_content_policy("external_classifier", custom)

    firings = evaluate_content_policies("any input", [custom])
    assert len(firings) == 1
    assert firings[0].name == "external_classifier"

    envelope = build_aggregate_refusal_envelope(firings)
    assert envelope.policy == "external_classifier"
    assert envelope.metadata["primary_policy"] == "external_classifier"
