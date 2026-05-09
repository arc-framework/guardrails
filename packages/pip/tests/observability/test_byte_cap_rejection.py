"""BoundedRedactor rejects values exceeding ``max_attribute_bytes``.

Direct redactor unit test (rather than full pipeline drive) to keep
the assertion crisp: a value larger than the configured cap must be
dropped with ``reason="exceeds_byte_cap"``.
"""

from __future__ import annotations

from arc_guard_core.observability_config import ObservabilityConfig

from arc_guard.observability import (
    REASON_EXCEEDS_BYTE_CAP,
    BoundedRedactor,
)


def test_byte_cap_rejects_oversized_value() -> None:
    config = ObservabilityConfig(max_attribute_bytes=64)
    redactor = BoundedRedactor(config)

    # repr of an 80-character string is 82 bytes (with quotes).
    big_value = "x" * 80
    result = redactor.sanitize("custom_key", big_value)

    assert result.accepted is False
    assert result.reason == REASON_EXCEEDS_BYTE_CAP


def test_byte_cap_accepts_under_threshold_value() -> None:
    config = ObservabilityConfig(max_attribute_bytes=128)
    redactor = BoundedRedactor(config)

    result = redactor.sanitize("custom_key", "short")

    assert result.accepted is True
    assert result.value == "short"
