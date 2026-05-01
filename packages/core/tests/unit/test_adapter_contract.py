"""T058 — Adapter boundary validators (FR-019)."""

from __future__ import annotations

import pytest

from arc_guard_core._adapter_contract import (
    validate_adapter_input,
    validate_adapter_output,
    validate_reporter_input,
)
from arc_guard_core.exceptions import AdapterBoundaryValidationError
from arc_guard_core.types import GuardResult


def test_adapter_input_must_be_mapping() -> None:
    with pytest.raises(AdapterBoundaryValidationError) as excinfo:
        validate_adapter_input(["not-a-mapping"], expected_kind="reporter")
    assert excinfo.value.code == "adapter.invalid_input"


def test_adapter_input_must_have_operation() -> None:
    with pytest.raises(AdapterBoundaryValidationError) as excinfo:
        validate_adapter_input({"foo": "bar"}, expected_kind="reporter")
    assert excinfo.value.code == "adapter.invalid_input"


def test_adapter_input_valid() -> None:
    validate_adapter_input({"operation": "publish", "x": 1}, expected_kind="reporter")


def test_adapter_output_type_mismatch_rejected() -> None:
    with pytest.raises(AdapterBoundaryValidationError) as excinfo:
        validate_adapter_output("not-a-GuardResult", expected_type=GuardResult)
    assert excinfo.value.code == "adapter.invalid_output"


def test_reporter_input_requires_guard_result() -> None:
    with pytest.raises(AdapterBoundaryValidationError):
        validate_reporter_input({"text": "x"})


def test_reporter_input_valid() -> None:
    result = GuardResult(text="x")
    validate_reporter_input(result)
