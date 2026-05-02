"""Schema/invariants for ``RehydrationVerdict``."""

from __future__ import annotations

import dataclasses

import pytest

from arc_guard_core.protocols.rehydration_verifier import RehydrationVerdict


def test_accept_verdict_round_trips() -> None:
    v = RehydrationVerdict(decision="accept", reason="all_checks_passed")
    assert v.decision == "accept"
    assert v.reason == "all_checks_passed"
    assert v.per_placeholder == {}


def test_reject_verdict_round_trips() -> None:
    v = RehydrationVerdict(decision="reject", reason="structural_shift")
    assert v.decision == "reject"


def test_partial_requires_per_placeholder_non_empty() -> None:
    with pytest.raises(ValueError, match="non-empty per_placeholder"):
        RehydrationVerdict(decision="partial", reason="partial_verdict")


def test_non_partial_must_have_empty_per_placeholder() -> None:
    with pytest.raises(ValueError, match="must be empty unless decision='partial'"):
        RehydrationVerdict(
            decision="accept",
            reason="ok",
            per_placeholder={"[A]": True},
        )


def test_frozen_rejects_mutation() -> None:
    v = RehydrationVerdict(decision="accept", reason="ok")
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.decision = "reject"  # type: ignore[misc]
