"""Aggregate evaluation across multiple ContentPolicy instances.

Two stub policies both match the same input. The pipeline contract
requires every configured policy to evaluate (no short-circuit on first
match) and the aggregate refusal envelope to cite every firing in
``metadata.firing_policies`` while using the first firing's
``RefusalCode`` as the primary code.
"""

from __future__ import annotations

from arc_guard_core.protocols.content_policy import ContentPolicyDecision
from arc_guard_core.refusal.codes import RefusalCode

from arc_guard.content_policies.aggregate import (
    build_aggregate_refusal_envelope,
    build_finding_metadata,
    evaluate_content_policies,
)
from arc_guard.content_policies.registry import (
    _reset_for_testing,
    register_content_policy,
)


class _AlwaysFiringPolicy:
    """Stub content policy whose evaluate() always matches."""

    def __init__(
        self,
        name: str,
        confidence: float,
        refusal_code: RefusalCode,
    ) -> None:
        self.name = name
        self._confidence = confidence
        self._refusal_code = refusal_code

    def evaluate(self, text: str) -> ContentPolicyDecision:
        return ContentPolicyDecision(
            matched=True,
            confidence=self._confidence,
            policy_name=self.name,
            refusal_code=self._refusal_code,
        )


class _NeverFiringPolicy:
    """Stub content policy whose evaluate() never matches."""

    def __init__(self, name: str) -> None:
        self.name = name

    def evaluate(self, text: str) -> ContentPolicyDecision:
        return ContentPolicyDecision(matched=False, policy_name=self.name)


def test_two_matching_policies_both_recorded() -> None:
    _reset_for_testing()
    p1 = _AlwaysFiringPolicy(
        name="competitor_pricing",
        confidence=0.92,
        refusal_code=RefusalCode.POLICY_BLOCK,
    )
    p2 = _AlwaysFiringPolicy(
        name="legal_advice",
        confidence=0.88,
        refusal_code=RefusalCode.POLICY_BLOCK,
    )
    register_content_policy("competitor_pricing", p1)
    register_content_policy("legal_advice", p2)

    firings = evaluate_content_policies("any matched text", [p1, p2])
    assert len(firings) == 2
    names = [f.name for f in firings]
    assert names == ["competitor_pricing", "legal_advice"]


def test_envelope_primary_code_matches_first_fired_policy() -> None:
    _reset_for_testing()
    p1 = _AlwaysFiringPolicy(
        name="first_to_fire",
        confidence=0.9,
        refusal_code=RefusalCode.PII_CRITICAL,
    )
    p2 = _AlwaysFiringPolicy(
        name="second_to_fire",
        confidence=0.85,
        refusal_code=RefusalCode.POLICY_BLOCK,
    )

    firings = evaluate_content_policies("input", [p1, p2])
    envelope = build_aggregate_refusal_envelope(firings)
    assert envelope.code == RefusalCode.PII_CRITICAL.value
    assert envelope.policy == "first_to_fire"
    assert envelope.metadata["primary_policy"] == "first_to_fire"


def test_envelope_metadata_lists_every_firing_policy() -> None:
    _reset_for_testing()
    p1 = _AlwaysFiringPolicy(
        name="alpha",
        confidence=0.91,
        refusal_code=RefusalCode.POLICY_BLOCK,
    )
    p2 = _AlwaysFiringPolicy(
        name="beta",
        confidence=0.82,
        refusal_code=RefusalCode.POLICY_BLOCK,
    )

    firings = evaluate_content_policies("input", [p1, p2])
    envelope = build_aggregate_refusal_envelope(firings)
    firing_payload = envelope.metadata["firing_policies"]
    assert isinstance(firing_payload, list)
    assert [entry["name"] for entry in firing_payload] == ["alpha", "beta"]
    assert all("refusal_code" in entry for entry in firing_payload)
    assert firing_payload[0]["confidence"] == 0.91


def test_non_matching_policies_do_not_appear_in_firings() -> None:
    _reset_for_testing()
    matching = _AlwaysFiringPolicy(
        name="matched_policy",
        confidence=0.99,
        refusal_code=RefusalCode.POLICY_BLOCK,
    )
    non_matching = _NeverFiringPolicy(name="silent_policy")

    firings = evaluate_content_policies("input", [matching, non_matching])
    assert len(firings) == 1
    assert firings[0].name == "matched_policy"


def test_no_short_circuit_every_policy_evaluated() -> None:
    """The aggregate evaluation contract forbids short-circuit. This
    test wires a tracking stub so we can assert every policy's
    ``evaluate()`` is called even after the first one matches.
    """

    _reset_for_testing()
    call_log: list[str] = []

    class _TrackingPolicy:
        def __init__(self, name: str, fires: bool) -> None:
            self.name = name
            self._fires = fires

        def evaluate(self, text: str) -> ContentPolicyDecision:
            call_log.append(self.name)
            if self._fires:
                return ContentPolicyDecision(
                    matched=True,
                    confidence=0.95,
                    policy_name=self.name,
                    refusal_code=RefusalCode.POLICY_BLOCK,
                )
            return ContentPolicyDecision(
                matched=False,
                policy_name=self.name,
            )

    p1 = _TrackingPolicy(name="first", fires=True)
    p2 = _TrackingPolicy(name="second", fires=True)
    p3 = _TrackingPolicy(name="third", fires=False)

    evaluate_content_policies("input", [p1, p2, p3])
    assert call_log == ["first", "second", "third"]


def test_finding_metadata_includes_policy_and_exemplar_set_id() -> None:
    _reset_for_testing()

    class _CustomPolicyWithExemplars:
        name = "topic_with_exemplars"
        exemplars = ("a", "b", "c")

        def evaluate(self, text: str) -> ContentPolicyDecision:
            return ContentPolicyDecision(
                matched=True,
                confidence=0.91,
                policy_name=self.name,
                refusal_code=RefusalCode.POLICY_BLOCK,
            )

    policy = _CustomPolicyWithExemplars()
    firings = evaluate_content_policies("input", [policy])
    metadata = build_finding_metadata(firings[0])
    assert metadata["policy"] == "topic_with_exemplars"
    assert isinstance(metadata["exemplar_set_id"], str)
    assert len(metadata["exemplar_set_id"]) == 16
    assert metadata["similarity"] == 0.91
