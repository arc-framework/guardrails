"""T055 — API boundary request validation."""

from __future__ import annotations

import pytest
from arc_guard_core.exceptions import ApiBoundaryValidationError

from arc_guard_service.validators import validate_request_payload


def test_minimal_payload_validates() -> None:
    gi = validate_request_payload({"text": "hello"})
    assert gi.text == "hello"
    assert gi.context.source == "input"
    assert gi.policy_hints == frozenset()


def test_full_payload_validates() -> None:
    gi = validate_request_payload(
        {
            "text": "hi",
            "context": {
                "source": "output",
                "user_id": "u1",
                "session_id": "s1",
                "correlation_id": "trace-1",
                "metadata": {"k": "v"},
            },
            "policy_hints": ["strict"],
        }
    )
    assert gi.context.source == "output"
    assert gi.context.correlation_id == "trace-1"
    assert "strict" in gi.policy_hints


def test_missing_text_rejected() -> None:
    with pytest.raises(ApiBoundaryValidationError) as excinfo:
        validate_request_payload({})
    assert excinfo.value.code == "api.missing_field"
    assert excinfo.value.details["field"] == "text"


def test_text_wrong_type_rejected() -> None:
    with pytest.raises(ApiBoundaryValidationError) as excinfo:
        validate_request_payload({"text": 42})
    assert excinfo.value.code == "api.type_mismatch"
    assert excinfo.value.details["field"] == "text"


def test_unknown_top_level_field_rejected() -> None:
    with pytest.raises(ApiBoundaryValidationError) as excinfo:
        validate_request_payload({"text": "ok", "rogue": True})
    assert excinfo.value.code == "api.unknown_field"
    assert "rogue" in excinfo.value.details["fields"]


def test_unknown_context_field_rejected() -> None:
    with pytest.raises(ApiBoundaryValidationError) as excinfo:
        validate_request_payload({"text": "x", "context": {"weird": 1}})
    assert excinfo.value.code == "api.unknown_field"


def test_invalid_context_source_rejected() -> None:
    with pytest.raises(ApiBoundaryValidationError) as excinfo:
        validate_request_payload({"text": "x", "context": {"source": "sideways"}})
    assert excinfo.value.code == "api.type_mismatch"


def test_policy_hints_must_be_array() -> None:
    with pytest.raises(ApiBoundaryValidationError):
        validate_request_payload({"text": "x", "policy_hints": "not-a-list"})


def test_payload_must_be_mapping() -> None:
    with pytest.raises(ApiBoundaryValidationError):
        validate_request_payload(["text", "hello"])  # type: ignore[arg-type]
