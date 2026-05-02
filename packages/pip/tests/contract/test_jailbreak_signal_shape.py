"""``JailbreakSignal`` schema + invariants."""

from __future__ import annotations

import dataclasses

import pytest

from arc_guard_core.jailbreak import JailbreakSignal


def test_valid_signal_round_trips() -> None:
    sig = JailbreakSignal(
        category="role_play",
        confidence=0.5,
        evidence_reference="ROLE_PLAY_1",
        detector_id="rule-based:1",
    )
    assert sig.category == "role_play"
    assert sig.confidence == 0.5


def test_confidence_above_one_rejected() -> None:
    with pytest.raises(ValueError, match="must be in"):
        JailbreakSignal(
            category="role_play",
            confidence=1.5,
            evidence_reference="X",
            detector_id="d:1",
        )


def test_confidence_below_zero_rejected() -> None:
    with pytest.raises(ValueError, match="must be in"):
        JailbreakSignal(
            category="role_play",
            confidence=-0.1,
            evidence_reference="X",
            detector_id="d:1",
        )


def test_boundary_confidence_values_legal() -> None:
    JailbreakSignal(
        category="role_play",
        confidence=0.0,
        evidence_reference="A",
        detector_id="d:1",
    )
    JailbreakSignal(
        category="role_play",
        confidence=1.0,
        evidence_reference="A",
        detector_id="d:1",
    )


def test_empty_evidence_reference_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        JailbreakSignal(
            category="role_play",
            confidence=0.5,
            evidence_reference="",
            detector_id="d:1",
        )


def test_evidence_reference_with_lowercase_rejected() -> None:
    """Runtime regex enforces ``[A-Z][A-Z0-9_]*`` so raw text can't smuggle."""
    with pytest.raises(ValueError, match=r"\[A-Z\]\[A-Z0-9_\]\*"):
        JailbreakSignal(
            category="role_play",
            confidence=0.5,
            evidence_reference="role play marker",
            detector_id="d:1",
        )


def test_evidence_reference_starting_with_digit_rejected() -> None:
    with pytest.raises(ValueError, match=r"\[A-Z\]\[A-Z0-9_\]\*"):
        JailbreakSignal(
            category="role_play",
            confidence=0.5,
            evidence_reference="1MARKER",
            detector_id="d:1",
        )


def test_empty_detector_id_rejected() -> None:
    with pytest.raises(ValueError, match="detector_id must be non-empty"):
        JailbreakSignal(
            category="role_play",
            confidence=0.5,
            evidence_reference="X",
            detector_id="",
        )


def test_frozen_rejects_mutation() -> None:
    sig = JailbreakSignal(
        category="role_play",
        confidence=0.5,
        evidence_reference="X",
        detector_id="d:1",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        sig.confidence = 0.7  # type: ignore[misc]
