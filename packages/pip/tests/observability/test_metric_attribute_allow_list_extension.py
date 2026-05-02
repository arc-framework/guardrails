"""Operator-extended allow-list admits custom metric keys.

Default allow-list omits ``"custom_widget"``; emitting a metric with
that key drops it. After extending the allow-list at config-construction
time, the same emission keeps the key.

Pairs with ``test_metric_allow_list_rejection.py`` from the payload-safety
suite — that test exercises the *default* allow-list's rejection path;
this one exercises the operator's *extension* path.
"""

from __future__ import annotations

from arc_guard_core.observability_config import ObservabilityConfig

from arc_guard.observability import BoundedRedactor


def test_default_allow_list_rejects_custom_key() -> None:
    redactor = BoundedRedactor(ObservabilityConfig())
    result = redactor.sanitize_metric_label("custom_widget", "wrench")
    assert result.accepted is False


def test_extended_allow_list_admits_custom_key() -> None:
    config = ObservabilityConfig(
        metric_attribute_allow_list=frozenset({
            "correlation_id",
            "stage",
            "custom_widget",
        }),
    )
    redactor = BoundedRedactor(config)
    result = redactor.sanitize_metric_label("custom_widget", "wrench")

    assert result.accepted is True
    assert result.value == "wrench"


def test_extended_allow_list_must_include_required_keys() -> None:
    """Validation rule: allow-list must contain at least the required
    base keys. An extension that drops them fails construction.
    """
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ObservabilityConfig(
            metric_attribute_allow_list=frozenset({"custom_widget"}),
        )
