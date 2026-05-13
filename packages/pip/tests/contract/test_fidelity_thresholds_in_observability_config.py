"""``ObservabilityConfig`` exposes ``fidelity_thresholds`` as a config knob."""

from __future__ import annotations

from arc_guard_core.observability_config import (
    FidelityThresholds,
    ObservabilityConfig,
)


def test_default_observability_config_returns_default_thresholds() -> None:
    config = ObservabilityConfig()
    assert config.fidelity_thresholds.warn == 0.7
    assert config.fidelity_thresholds.clarify == 0.5
    assert config.fidelity_thresholds.refuse == 0.3


def test_custom_thresholds_round_trip_through_config() -> None:
    config = ObservabilityConfig(
        fidelity_thresholds=FidelityThresholds(
            warn=0.8,
            clarify=0.4,
            refuse=0.2,
        ),
    )
    assert config.fidelity_thresholds.warn == 0.8
    assert config.fidelity_thresholds.clarify == 0.4
    assert config.fidelity_thresholds.refuse == 0.2


def test_thresholds_are_frozen() -> None:
    """Pydantic frozen=True — assignment to a field after construction raises."""
    import pytest
    from pydantic import ValidationError

    config = ObservabilityConfig()
    with pytest.raises((ValidationError, AttributeError, TypeError)):
        config.fidelity_thresholds.warn = 0.99  # type: ignore[misc]
