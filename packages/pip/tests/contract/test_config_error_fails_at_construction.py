"""Config errors fail at construction time, never at first-request time.

Invalid ``ObservabilityConfig`` field values raise pydantic
``ValidationError`` at construction, so a misconfigured pipeline can
never be built. The dynamic-registration counterpart
(``RegistryFrozenError``) is covered by the registry-freeze test under
``tests/concurrency/`` when the concurrency hardening lands.
"""

from __future__ import annotations

import pytest
from arc_guard_core.observability_config import ObservabilityConfig
from pydantic import ValidationError


def test_invalid_sampling_rate_above_one() -> None:
    with pytest.raises(ValidationError):
        ObservabilityConfig(sampling_rate=1.5)


def test_invalid_sampling_rate_negative() -> None:
    with pytest.raises(ValidationError):
        ObservabilityConfig(sampling_rate=-0.1)


def test_invalid_log_level_floor() -> None:
    with pytest.raises(ValidationError):
        ObservabilityConfig(log_level_floor="critical")


def test_max_attribute_bytes_below_minimum() -> None:
    with pytest.raises(ValidationError):
        ObservabilityConfig(max_attribute_bytes=32)


def test_metric_attribute_allow_list_missing_required_keys() -> None:
    with pytest.raises(ValidationError):
        ObservabilityConfig(metric_attribute_allow_list=frozenset({"only_one"}))
