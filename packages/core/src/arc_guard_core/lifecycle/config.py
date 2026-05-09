"""Payload-capture policy for lifecycle events.

By default, lifecycle events carry only sizes/lengths/entity types — no
raw text. The policy lets operators opt into richer capture in two
distinct buckets:

- `should_capture_sanitized()` — capture POST-sanitization text (the
  version with PII placeholders applied). Lower risk: the captured text
  has already been masked by the same sanitization logic the pipeline
  applies to the LLM's input.

- `should_capture_raw_input()` — capture raw inbound user text on
  `RequestStarted` events. Higher risk: PII reaches the audit channel.
  Documented as security-sensitive; should only be enabled when the
  dashboard / sink is appropriately authenticated.

Both flags are independent. Operators can enable sanitized capture
without raw capture; raw capture without sanitized is unusual but legal.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PayloadCapturePolicy(Protocol):
    """Decides whether a given lifecycle emission may include raw text.

    Implementations MUST be cheap (called per-emission). Stateless or
    read-once-and-cache patterns recommended.
    """

    def should_capture_sanitized(self) -> bool:
        """Return True to permit POST-sanitization text in event payloads."""
        ...

    def should_capture_raw_input(self) -> bool:
        """Return True to permit raw inbound user text in event payloads."""
        ...


class NullPayloadCapturePolicy:
    """Default policy: capture nothing. Sizes / lengths / entity types
    only. Constitutionally aligned with Principle V (default events MUST
    avoid raw sensitive payloads)."""

    def should_capture_sanitized(self) -> bool:
        return False

    def should_capture_raw_input(self) -> bool:
        return False


__all__ = ["PayloadCapturePolicy", "NullPayloadCapturePolicy"]
