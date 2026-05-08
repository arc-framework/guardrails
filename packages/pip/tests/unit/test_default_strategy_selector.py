"""Unit tests for DefaultStrategySelector.

Covers the documented entity-type to strategy-name mapping, the safe
default fallback for unmapped types, the structured observability event
emitted on the fallback path, and the constructor override-mapping
precedence.
"""

from __future__ import annotations

from typing import Any

import pytest
from arc_guard_core.types import Finding, GuardResult, RiskLevel

from arc_guard.selectors.default import DefaultStrategySelector


class _RecordingLogger:
    """In-test logger that records every ``event()`` call."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def bind(self, **fields: Any) -> _RecordingLogger:
        return self

    def event(self, name: str, *, level: str = "info", **fields: Any) -> None:
        self.events.append((name, {"level": level, **fields}))


def _make_finding(entity_type: str) -> Finding:
    return Finding(
        entity_type=entity_type,
        start=0,
        end=5,
        risk_level=RiskLevel.MEDIUM,
        inspector="test",
    )


def _make_result(text: str = "hello") -> GuardResult:
    return GuardResult(text=text, action="pass", findings=())


_DOCUMENTED_MAPPING: list[tuple[str, str]] = [
    ("EMAIL_ADDRESS", "redact"),
    ("PHONE_NUMBER", "redact"),
    ("PERSON", "redact"),
    ("LOCATION", "redact"),
    ("US_SSN", "hash"),
    ("US_DRIVER_LICENSE", "hash"),
    ("US_PASSPORT", "hash"),
    ("IBAN_CODE", "hash"),
    ("IP_ADDRESS", "hash"),
    ("CREDIT_CARD", "block"),
    ("US_BANK_NUMBER", "block"),
    ("API_KEY", "block"),
    ("PASSWORD", "block"),
    ("BEARER_TOKEN", "block"),
    ("EMPLOYEE_ID", "tokenize"),
    ("INTERNAL_PROJECT_CODE", "tokenize"),
    ("CUSTOMER_ID", "tokenize"),
    ("URL", "warn"),
    ("DATE_TIME", "warn"),
    ("NRP", "warn"),
]


@pytest.mark.parametrize(("entity_type", "expected_strategy"), _DOCUMENTED_MAPPING)
def test_documented_mapping_returns_expected_strategy(
    entity_type: str, expected_strategy: str
) -> None:
    selector = DefaultStrategySelector()
    finding = _make_finding(entity_type)
    assert selector.select(finding, _make_result()) == expected_strategy


def test_default_mapping_is_immutable() -> None:
    with pytest.raises(TypeError):
        DefaultStrategySelector.DEFAULT_MAPPING["NEW_TYPE"] = "block"  # type: ignore[index]


def test_default_mapping_class_attribute_matches_documented_table() -> None:
    expected = dict(_DOCUMENTED_MAPPING)
    assert dict(DefaultStrategySelector.DEFAULT_MAPPING) == expected


def test_unmapped_entity_falls_back_to_redact() -> None:
    selector = DefaultStrategySelector()
    finding = _make_finding("DEFINITELY_NOT_A_MAPPED_TYPE")
    assert selector.select(finding, _make_result()) == "redact"


def test_unmapped_entity_emits_documented_logger_event() -> None:
    recorder = _RecordingLogger()
    selector = DefaultStrategySelector(logger=recorder)
    finding = _make_finding("DEFINITELY_NOT_A_MAPPED_TYPE")

    selector.select(finding, _make_result())

    assert len(recorder.events) == 1
    name, fields = recorder.events[0]
    assert name == "guard.selector.unmapped_entity_type"
    assert fields["level"] == "warning"
    assert fields["selector"] == "default"
    assert fields["entity_type"] == "DEFINITELY_NOT_A_MAPPED_TYPE"
    assert fields["fallback_strategy"] == "redact"


def test_mapped_entity_does_not_emit_logger_event() -> None:
    recorder = _RecordingLogger()
    selector = DefaultStrategySelector(logger=recorder)
    finding = _make_finding("EMAIL_ADDRESS")

    selector.select(finding, _make_result())

    assert recorder.events == []


def test_constructor_override_mapping_takes_precedence() -> None:
    custom_mapping = {
        **DefaultStrategySelector.DEFAULT_MAPPING,
        "EMAIL_ADDRESS": "block",
        "MY_CUSTOM_TYPE": "tokenize",
    }
    selector = DefaultStrategySelector(mapping=custom_mapping)

    assert selector.select(_make_finding("EMAIL_ADDRESS"), _make_result()) == "block"
    assert selector.select(_make_finding("MY_CUSTOM_TYPE"), _make_result()) == "tokenize"
    assert selector.select(_make_finding("US_SSN"), _make_result()) == "hash"


def test_override_mapping_unmapped_still_falls_back_to_redact() -> None:
    custom_mapping = {"ONLY_THIS_TYPE": "block"}
    recorder = _RecordingLogger()
    selector = DefaultStrategySelector(mapping=custom_mapping, logger=recorder)

    assert selector.select(_make_finding("ONLY_THIS_TYPE"), _make_result()) == "block"
    assert selector.select(_make_finding("EMAIL_ADDRESS"), _make_result()) == "redact"

    assert len(recorder.events) == 1
    assert recorder.events[0][0] == "guard.selector.unmapped_entity_type"
    assert recorder.events[0][1]["entity_type"] == "EMAIL_ADDRESS"
