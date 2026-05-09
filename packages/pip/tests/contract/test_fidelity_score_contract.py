"""``FidelityScore`` schema + invariants."""

from __future__ import annotations

import dataclasses

import pytest
from arc_guard_core.fidelity import NOT_MEASURED, FidelityScore


def test_measured_constructor_round_trips() -> None:
    score = FidelityScore.measured(0.5)
    assert score.value == 0.5
    assert score.sentinel == "measured"


def test_not_measured_constructor_returns_sentinel_shape() -> None:
    score = FidelityScore.not_measured()
    assert score.value is None
    assert score.sentinel == "not_measured"


def test_measured_with_out_of_range_value_raises() -> None:
    with pytest.raises(ValueError, match="must be in"):
        FidelityScore.measured(1.5)
    with pytest.raises(ValueError, match="must be in"):
        FidelityScore.measured(-0.1)


def test_measured_boundaries_are_legal() -> None:
    FidelityScore.measured(0.0)
    FidelityScore.measured(1.0)


def test_measured_with_none_value_raises() -> None:
    with pytest.raises(ValueError, match="requires a value"):
        FidelityScore(value=None, sentinel="measured")


def test_not_measured_with_value_raises() -> None:
    with pytest.raises(ValueError, match="must have value=None"):
        FidelityScore(value=0.5, sentinel="not_measured")


def test_frozen_rejects_mutation() -> None:
    score = FidelityScore.measured(0.5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        score.value = 0.7  # type: ignore[misc]


def test_module_level_singleton_matches_constructor() -> None:
    assert NOT_MEASURED == FidelityScore.not_measured()
    assert NOT_MEASURED.sentinel == "not_measured"
    assert NOT_MEASURED.value is None
