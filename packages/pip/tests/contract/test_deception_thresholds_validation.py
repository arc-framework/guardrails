"""``DeceptionThresholds`` rejects invalid combinations at construction.

INVERSE direction relative to ``FidelityThresholds``: ``refuse > clarify > warn``
(higher score = MORE deception, worse). Tests document this expectation.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arc_guard_core.observability_config import DeceptionThresholds


def test_refuse_above_one_rejected() -> None:
    with pytest.raises(ValidationError):
        DeceptionThresholds(refuse=1.5, clarify=0.5, warn=0.3)


def test_warn_below_zero_rejected() -> None:
    with pytest.raises(ValidationError):
        DeceptionThresholds(refuse=0.7, clarify=0.5, warn=-0.1)


def test_refuse_below_clarify_rejected() -> None:
    """INVERSE direction: refuse must be > clarify."""
    with pytest.raises(ValidationError, match="refuse > clarify > warn"):
        DeceptionThresholds(refuse=0.3, clarify=0.5, warn=0.2)


def test_clarify_below_warn_rejected() -> None:
    with pytest.raises(ValidationError, match="refuse > clarify > warn"):
        DeceptionThresholds(refuse=0.7, clarify=0.2, warn=0.4)


def test_equal_thresholds_rejected() -> None:
    with pytest.raises(ValidationError):
        DeceptionThresholds(refuse=0.5, clarify=0.5, warn=0.3)


def test_boundary_values_accepted() -> None:
    thresholds = DeceptionThresholds(refuse=1.0, clarify=0.5, warn=0.0)
    assert thresholds.refuse == 1.0
    assert thresholds.warn == 0.0


def test_defaults_match_documented_values() -> None:
    """Default tuple is (refuse=0.7, clarify=0.5, warn=0.3)."""
    thresholds = DeceptionThresholds()
    assert thresholds.refuse == 0.7
    assert thresholds.clarify == 0.5
    assert thresholds.warn == 0.3
