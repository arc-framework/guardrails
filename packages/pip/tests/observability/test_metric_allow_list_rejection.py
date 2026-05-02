"""FR-025: BoundedRedactor enforces metric attribute allow-list.

Span attributes pass through with byte-cap and substring-search only.
Metric labels additionally enforce
``ObservabilityConfig.metric_attribute_allow_list``: any key not in the
list is dropped with ``reason="not_in_allow_list"``.
"""

from __future__ import annotations

from arc_guard_core.observability_config import ObservabilityConfig

from arc_guard.observability import (
    REASON_NOT_IN_ALLOW_LIST,
    BoundedRedactor,
)


def test_metric_path_rejects_out_of_allow_list_key() -> None:
    redactor = BoundedRedactor(ObservabilityConfig())  # default allow-list
    result = redactor.sanitize_metric_label("user_email_domain", "example.com")

    assert result.accepted is False
    assert result.reason == REASON_NOT_IN_ALLOW_LIST


def test_metric_path_accepts_allow_listed_key() -> None:
    redactor = BoundedRedactor(ObservabilityConfig())
    # ``stage`` is in the default allow-list.
    result = redactor.sanitize_metric_label("stage", "validate")

    assert result.accepted is True
    assert result.value == "validate"


def test_span_path_does_not_enforce_allow_list() -> None:
    redactor = BoundedRedactor(ObservabilityConfig())

    # Same key that ``sanitize_metric_label`` rejects passes through here.
    result = redactor.sanitize("user_email_domain", "example.com")
    assert result.accepted is True


def test_extending_allow_list_admits_custom_key() -> None:
    config = ObservabilityConfig(
        metric_attribute_allow_list=frozenset({
            "correlation_id",
            "stage",
            "custom_widget",  # operator-added
        }),
    )
    redactor = BoundedRedactor(config)

    result = redactor.sanitize_metric_label("custom_widget", "wrench")

    assert result.accepted is True
    assert result.value == "wrench"
