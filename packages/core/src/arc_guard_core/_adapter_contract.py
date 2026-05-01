"""Adapter boundary validation helpers (FR-019).

Adapters (NATS, Unleash, OTEL, webhook reporters, model-backed inspectors)
implement Protocols defined in ``arc_guard_core.protocols``. Their inputs and
outputs MUST be validated against typed models before and after every external
call. These helpers are the canonical validators.

The functions here are deliberately small and side-effect-free; concrete
adapters call them at the right moments. The contract test suite asserts
that any failure surfaces as ``AdapterBoundaryValidationError`` (see
``contracts/exceptions.md``).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from arc_guard_core.exceptions import AdapterBoundaryValidationError
from arc_guard_core.types import GuardResult


def validate_adapter_input(payload: Any, *, expected_kind: str) -> None:
    """Validate that *payload* is shaped correctly for an adapter input.

    Currently checks only that the payload is a mapping and contains an
    ``operation`` discriminator. Specific adapters extend this with per-op
    rules.
    """
    if not isinstance(payload, Mapping):
        raise AdapterBoundaryValidationError(
            f"adapter input must be a mapping (kind={expected_kind})",
            code="adapter.invalid_input",
            details={"got": type(payload).__name__, "expected_kind": expected_kind},
        )
    if "operation" not in payload:
        raise AdapterBoundaryValidationError(
            "adapter input missing 'operation' discriminator",
            code="adapter.invalid_input",
            details={"expected_kind": expected_kind},
        )


def validate_adapter_output(value: Any, *, expected_type: type) -> None:
    """Validate that *value* matches the typed model the adapter promised."""
    if not isinstance(value, expected_type):
        raise AdapterBoundaryValidationError(
            f"adapter output expected {expected_type.__qualname__}",
            code="adapter.invalid_output",
            details={
                "expected": expected_type.__qualname__,
                "got": type(value).__name__,
            },
        )


def validate_reporter_input(result: Any) -> None:
    """Reporters receive a typed ``GuardResult``; nothing else is acceptable."""
    if not isinstance(result, GuardResult):
        raise AdapterBoundaryValidationError(
            "reporter input must be a GuardResult",
            code="adapter.invalid_input",
            details={"expected": "GuardResult", "got": type(result).__name__},
        )


__all__ = [
    "validate_adapter_input",
    "validate_adapter_output",
    "validate_reporter_input",
]
