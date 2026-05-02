"""``ObservabilityConfig`` exposes both new threshold types as config knobs."""

from __future__ import annotations

from arc_guard_core.observability_config import (
    DeceptionThresholds,
    JailbreakThresholds,
    ObservabilityConfig,
)


def test_default_observability_config_returns_default_jailbreak_thresholds() -> None:
    config = ObservabilityConfig()
    assert config.jailbreak_thresholds.refuse == 0.8
    assert config.jailbreak_thresholds.clarify == 0.6
    assert config.jailbreak_thresholds.warn == 0.4


def test_default_observability_config_returns_default_deception_thresholds() -> None:
    config = ObservabilityConfig()
    assert config.deception_thresholds.refuse == 0.7
    assert config.deception_thresholds.clarify == 0.5
    assert config.deception_thresholds.warn == 0.3


def test_custom_jailbreak_thresholds_round_trip() -> None:
    config = ObservabilityConfig(
        jailbreak_thresholds=JailbreakThresholds(
            refuse=0.9, clarify=0.7, warn=0.5,
        ),
    )
    assert config.jailbreak_thresholds.refuse == 0.9
    assert config.jailbreak_thresholds.clarify == 0.7
    assert config.jailbreak_thresholds.warn == 0.5


def test_custom_deception_thresholds_round_trip() -> None:
    config = ObservabilityConfig(
        deception_thresholds=DeceptionThresholds(
            refuse=0.6, clarify=0.4, warn=0.2,
        ),
    )
    assert config.deception_thresholds.refuse == 0.6
    assert config.deception_thresholds.clarify == 0.4
    assert config.deception_thresholds.warn == 0.2
