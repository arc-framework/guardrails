"""Typed placeholder registry.

The single source of truth for the labels emitted by the redact strategy.
Single-occurrence placeholders are unsuffixed (``[CREDIT_CARD]``); multi-
occurrence placeholders use a per-input, per-type sequential suffix
(``[CREDIT_CARD_1]``, ``[CREDIT_CARD_2]``, …).

Integrators register custom entity types via ``register_placeholder``.
"""

from __future__ import annotations

import re
import threading

_LABEL_RE = re.compile(r"^\[[A-Z][A-Z0-9_]*\]$")
_LOCK = threading.RLock()

DEFAULT_PLACEHOLDERS: dict[str, str] = {
    "EMPLOYEE_NAME": "[EMPLOYEE_NAME]",
    "CUSTOMER_NAME": "[CUSTOMER_NAME]",
    "INTERNAL_PROJECT": "[INTERNAL_PROJECT]",
    "CONFIDENTIAL_LOCATION": "[CONFIDENTIAL_LOCATION]",
    "EMAIL_ADDRESS": "[EMAIL_ADDRESS]",
    "PHONE_NUMBER": "[PHONE_NUMBER]",
    "CREDIT_CARD": "[CREDIT_CARD]",
    "US_SSN": "[US_SSN]",
    "IP_ADDRESS": "[IP_ADDRESS]",
    "UNKNOWN_PII": "[UNKNOWN_PII]",
}

_REGISTRY: dict[str, str] = dict(DEFAULT_PLACEHOLDERS)


def register_placeholder(entity_type: str, label: str) -> None:
    """Register or override a typed placeholder.

    Raises ValueError on empty ``entity_type`` or malformed ``label``.
    """
    if not entity_type:
        raise ValueError("entity_type must be non-empty")
    if not _LABEL_RE.match(label):
        raise ValueError(f"placeholder label {label!r} must match {_LABEL_RE.pattern}")
    with _LOCK:
        _REGISTRY[entity_type] = label


def get_placeholder(entity_type: str) -> str:
    """Return the registered label.

    For unknown entity types, synthesises ``[<ENTITY_TYPE>]`` on the fly so
    callers using custom entity types don't need to pre-register. The
    explicit ``UNKNOWN_PII`` registered label is used only when an
    inspector deliberately tags a finding with that entity type.
    """
    with _LOCK:
        if entity_type in _REGISTRY:
            return _REGISTRY[entity_type]
    return f"[{entity_type}]"


def list_registered() -> frozenset[str]:
    """Return all registered entity types (snapshot)."""
    with _LOCK:
        return frozenset(_REGISTRY.keys())


def format_placeholder(entity_type: str, occurrence: int, total: int) -> str:
    """Single-occurrence unsuffixed; multi-occurrence suffix ``_<N>``.

    ``occurrence`` is 1-indexed. Raises ValueError on bad inputs.
    """
    if total < 1:
        raise ValueError("total must be >= 1")
    if occurrence < 1 or occurrence > total:
        raise ValueError("occurrence must be in [1, total]")
    label = get_placeholder(entity_type)
    if total == 1:
        return label
    # Strip the closing ']' to insert the suffix
    return f"{label[:-1]}_{occurrence}]"


__all__ = [
    "DEFAULT_PLACEHOLDERS",
    "register_placeholder",
    "get_placeholder",
    "list_registered",
    "format_placeholder",
]
