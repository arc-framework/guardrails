"""Per-rid lifecycle event emitter.

Threading model: the api transport creates ONE `LifecycleEmitter` per
HTTP request, then passes it to the pipeline through
`GuardContext.metadata["_lifecycle_emitter"]`. The pipeline reads the
emitter when present and emits its own lifecycle events using the SAME
seq counter and rid as the transport-layer events.

This keeps the spec contract intact: every event for one rid has a
strictly increasing `seq` and a stable `rid`, regardless of which layer
(transport or pipeline-internal) emitted it.

Lives in `arc_guard_core` (not `arc_guard`) so both the pipeline and the
api transport can import it without crossing the layered-import boundary.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from arc_guard_core.lifecycle._ulid import new_event_id
from arc_guard_core.lifecycle.config import (
    NullPayloadCapturePolicy,
    PayloadCapturePolicy,
)
from arc_guard_core.lifecycle.events import LifecycleEventBase
from arc_guard_core.lifecycle.sink import LifecycleSink
from arc_guard_core.placeholders import DEFAULT_PLACEHOLDERS

_SCRUBBED_TEXT_FIELDS = ("text_before", "text_after", "response_text")
_SCRUB_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
        DEFAULT_PLACEHOLDERS["CREDIT_CARD"],
    ),
    (
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        DEFAULT_PLACEHOLDERS["US_SSN"],
    ),
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}\b"),
        DEFAULT_PLACEHOLDERS["EMAIL_ADDRESS"],
    ),
    (
        re.compile(r"\b(?:\+?\d[\d(). -]{7,}\d)\b"),
        DEFAULT_PLACEHOLDERS["PHONE_NUMBER"],
    ),
    (
        re.compile(r"\bpassport-[A-Za-z0-9]+\b", re.IGNORECASE),
        "passport-[US_PASSPORT]",
    ),
)


def _scrub_captured_text(value: str) -> str:
    scrubbed = value
    for pattern, replacement in _SCRUB_PATTERNS:
        scrubbed = pattern.sub(replacement, scrubbed)
    return scrubbed


class LifecycleEmitter:
    """Constructs typed lifecycle events with monotonic per-rid seq numbers
    and emits them through the configured sink.

    Concurrency: not thread-safe. One emitter per HTTP request.
    Failure mode: open. Sink failures are absorbed by the sink itself; the
    emitter does not catch.

    Carries a `PayloadCapturePolicy` so emission sites (in transport AND
    in the pipeline) can consult the same flags without re-walking
    settings. Default policy captures nothing.
    """

    __slots__ = ("_sink", "_rid", "_seq", "_policy")

    def __init__(
        self,
        sink: LifecycleSink,
        rid: str,
        policy: PayloadCapturePolicy | None = None,
    ) -> None:
        self._sink = sink
        self._rid = rid
        self._seq = 0
        self._policy: PayloadCapturePolicy = policy or NullPayloadCapturePolicy()

    @property
    def rid(self) -> str:
        return self._rid

    @property
    def sink(self) -> LifecycleSink:
        return self._sink

    @property
    def policy(self) -> PayloadCapturePolicy:
        return self._policy

    @property
    def next_seq_value(self) -> int:
        """Peek at the next seq without incrementing. Useful for tests."""
        return self._seq

    async def emit(
        self,
        event_class: type[LifecycleEventBase],
        *,
        parent_id: str | None,
        **fields: Any,
    ) -> LifecycleEventBase:
        if self._policy.should_capture_sanitized() and not self._policy.should_capture_raw_input():
            fields = {
                key: _scrub_captured_text(value)
                if key in _SCRUBBED_TEXT_FIELDS and isinstance(value, str)
                else value
                for key, value in fields.items()
            }
        seq = self._seq
        self._seq += 1
        event = event_class(
            id=new_event_id(),
            parent_id=parent_id,
            seq=seq,
            ts=datetime.now(UTC),
            rid=self._rid,
            **fields,
        )
        await self._sink.emit(event)  # type: ignore[arg-type]
        return event


__all__ = ["LifecycleEmitter"]
