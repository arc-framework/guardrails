"""Structural-conformance tests for the ``RehydrationVerifier`` Protocol."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from arc_guard_core.protocols import (
    RehydrationDecision,
    RehydrationVerdict,
    RehydrationVerifier,
)


class _StubVerifier:
    def verify(
        self,
        *,
        sanitized_prompt: str,
        rehydration_candidate: str,
        entity_map: Mapping[str, str],
    ) -> RehydrationVerdict:
        if "[INVENTED]" in rehydration_candidate:
            return RehydrationVerdict(
                decision="reject", reason="invented_placeholder",
            )
        return RehydrationVerdict(decision="accept", reason="all_checks_passed")


def test_rehydration_verifier_is_runtime_checkable() -> None:
    assert isinstance(_StubVerifier(), RehydrationVerifier)


def test_verdict_decision_is_one_of_three_literals() -> None:
    accept = RehydrationVerdict(decision="accept", reason="ok")
    reject = RehydrationVerdict(decision="reject", reason="invented_placeholder")
    partial = RehydrationVerdict(
        decision="partial",
        reason="partial_verdict",
        per_placeholder={"[A]": True, "[B]": False},
    )
    assert accept.decision == "accept"
    assert reject.decision == "reject"
    assert partial.decision == "partial"


def test_partial_decision_requires_per_placeholder() -> None:
    with pytest.raises(ValueError, match="non-empty per_placeholder"):
        RehydrationVerdict(decision="partial", reason="partial_verdict")


def test_non_partial_must_have_empty_per_placeholder() -> None:
    with pytest.raises(ValueError, match="must be empty unless decision='partial'"):
        RehydrationVerdict(
            decision="accept",
            reason="ok",
            per_placeholder={"[A]": True},
        )


def test_decision_literal_type() -> None:
    # Belt-and-suspenders: the discriminator type alias is exported.
    decision: RehydrationDecision = "accept"
    assert decision in {"accept", "reject", "partial"}
