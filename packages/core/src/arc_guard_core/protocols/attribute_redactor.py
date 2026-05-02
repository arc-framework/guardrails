"""Sanitize-or-reject contract for user-derived observability attributes.

Implementations decide whether to allow a span attribute, log field, or
metric label through to a backend. They MUST NOT raise — failure is
expressed by returning a ``RedactionResult`` with ``accepted=False`` and
a reason string, so observability paths stay non-blocking.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class RedactionResult:
    """Outcome of an attribute sanitization call.

    ``accepted=True`` means the attribute may be emitted with ``value``
    (which may differ from the input — e.g., truncated). ``accepted=False``
    means the attribute MUST be dropped; ``reason`` carries a stable
    string identifier suitable for the
    ``arc_guardrails.observability.attribute_dropped`` metric label.
    """

    accepted: bool
    value: Any | None = None
    reason: str | None = None


@runtime_checkable
class AttributeRedactor(Protocol):
    """Sanitize or reject a user-derived attribute value before emission.

    Concurrency: thread-safe.
    Failure mode: implementations must not raise; they return a
    ``RedactionResult`` with ``accepted=False`` instead.
    """

    def sanitize(self, key: str, value: Any) -> RedactionResult:
        ...


__all__ = [
    "RedactionResult",
    "AttributeRedactor",
]
