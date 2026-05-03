"""Threshold construction rejects invalid combinations at construction time."""

from __future__ import annotations

import pytest
from arc_guard_core.observability_config import FidelityThresholds
from pydantic import ValidationError


def test_warn_above_one_rejected() -> None:
    with pytest.raises(ValidationError):
        FidelityThresholds(warn=1.5, clarify=0.5, refuse=0.3)


def test_refuse_below_zero_rejected() -> None:
    with pytest.raises(ValidationError):
        FidelityThresholds(warn=0.7, clarify=0.5, refuse=-0.1)


def test_warn_below_clarify_rejected() -> None:
    with pytest.raises(ValidationError, match="warn > clarify > refuse"):
        FidelityThresholds(warn=0.5, clarify=0.7, refuse=0.3)


def test_clarify_below_refuse_rejected() -> None:
    with pytest.raises(ValidationError, match="warn > clarify > refuse"):
        FidelityThresholds(warn=0.7, clarify=0.5, refuse=0.6)


def test_equal_thresholds_rejected() -> None:
    """Strict ordering — equal values fail (not strictly greater)."""
    with pytest.raises(ValidationError):
        FidelityThresholds(warn=0.5, clarify=0.5, refuse=0.3)


def test_boundary_values_accepted() -> None:
    """``warn=1.0`` and ``refuse=0.0`` are legitimate operator settings."""
    thresholds = FidelityThresholds(warn=1.0, clarify=0.5, refuse=0.0)
    assert thresholds.warn == 1.0
    assert thresholds.refuse == 0.0


def test_defaults_match_spec() -> None:
    thresholds = FidelityThresholds()
    assert thresholds.warn == 0.7
    assert thresholds.clarify == 0.5
    assert thresholds.refuse == 0.3
