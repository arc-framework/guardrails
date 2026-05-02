"""``JailbreakThresholds`` rejects invalid combinations at construction.

INVERSE direction relative to ``FidelityThresholds``: ``refuse > clarify > warn``
(higher score = MORE risk). Tests document this expectation prominently.
"""

from __future__ import annotations

import pytest
from arc_guard_core.observability_config import JailbreakThresholds
from pydantic import ValidationError


def test_refuse_above_one_rejected() -> None:
    with pytest.raises(ValidationError):
        JailbreakThresholds(refuse=1.5, clarify=0.6, warn=0.4)


def test_warn_below_zero_rejected() -> None:
    with pytest.raises(ValidationError):
        JailbreakThresholds(refuse=0.8, clarify=0.6, warn=-0.1)


def test_refuse_below_clarify_rejected() -> None:
    """INVERSE direction: refuse must be > clarify."""
    with pytest.raises(ValidationError, match="refuse > clarify > warn"):
        JailbreakThresholds(refuse=0.3, clarify=0.5, warn=0.2)


def test_clarify_below_warn_rejected() -> None:
    """INVERSE direction: clarify must be > warn."""
    with pytest.raises(ValidationError, match="refuse > clarify > warn"):
        JailbreakThresholds(refuse=0.8, clarify=0.3, warn=0.5)


def test_equal_thresholds_rejected() -> None:
    """Strict ordering — equal values fail."""
    with pytest.raises(ValidationError):
        JailbreakThresholds(refuse=0.6, clarify=0.6, warn=0.4)


def test_boundary_values_accepted() -> None:
    """``refuse=1.0`` and ``warn=0.0`` are legitimate operator settings."""
    thresholds = JailbreakThresholds(refuse=1.0, clarify=0.5, warn=0.0)
    assert thresholds.refuse == 1.0
    assert thresholds.warn == 0.0


def test_defaults_match_documented_values() -> None:
    """Default tuple is (refuse=0.8, clarify=0.6, warn=0.4)."""
    thresholds = JailbreakThresholds()
    assert thresholds.refuse == 0.8
    assert thresholds.clarify == 0.6
    assert thresholds.warn == 0.4


def test_aggressive_thresholds_round_trip() -> None:
    """A conservative threshold tuple constructs and reads back."""
    thresholds = JailbreakThresholds(refuse=0.95, clarify=0.85, warn=0.7)
    assert thresholds.refuse == 0.95
    assert thresholds.clarify == 0.85
    assert thresholds.warn == 0.7
