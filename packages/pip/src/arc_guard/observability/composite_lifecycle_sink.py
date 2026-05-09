"""Fan-out helper that broadcasts every emission to multiple `LifecycleSink`
implementations with per-child failure isolation.

Operators wire `CompositeLifecycleSink([RingBufferLifecycleSink(...),
SqliteLifecycleSink(...), MyMongoLifecycleSink(...)])` to get every event
delivered to multiple stores simultaneously. A failing child does NOT
prevent siblings from receiving the event.

Lookup walks children in declaration order and returns the first non-None
list. The endpoint reads `last_served_from` to surface the actual tier
that served the response (`x-lifecycle-tier` HTTP header).
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from arc_guard_core.lifecycle import LifecycleEvent, LifecycleSink

_LOG = logging.getLogger("arc_guard.lifecycle.composite")


class CompositeLifecycleSink:
    """LifecycleSink: fan-out to N children with per-child failure isolation."""

    def __init__(self, sinks: list[LifecycleSink]) -> None:
        if not sinks:
            raise ValueError("CompositeLifecycleSink requires at least one child sink")
        self._sinks: list[LifecycleSink] = list(sinks)
        self._failures: Counter[str] = Counter()
        self.last_served_from: str = "composite-fallthrough"

    @property
    def failures(self) -> dict[str, int]:
        """Per-child failure counts keyed by class name. Read-only snapshot."""
        return dict(self._failures)

    def __len__(self) -> int:
        return len(self._sinks)

    async def emit(self, event: LifecycleEvent) -> None:
        for child in self._sinks:
            try:
                await child.emit(event)
            except Exception as exc:  # pragma: no cover — sink failure path
                cls_name = type(child).__name__
                self._failures[cls_name] += 1
                _LOG.warning(
                    "composite child %s.emit() raised (count=%d): %s",
                    cls_name,
                    self._failures[cls_name],
                    exc,
                )

    async def query(self, rid: str) -> list[LifecycleEvent] | None:
        """Walk children in order; return first non-None list. Updates
        `last_served_from` to the served tier label so the lookup endpoint
        can surface it via the `x-lifecycle-tier` response header.
        """
        for child in self._sinks:
            try:
                events = await child.query(rid)
            except Exception as exc:
                cls_name = type(child).__name__
                self._failures[cls_name] += 1
                _LOG.warning(
                    "composite child %s.query() raised (count=%d): %s",
                    cls_name,
                    self._failures[cls_name],
                    exc,
                )
                continue
            if events:
                self.last_served_from = _tier_label_for(child)
                return events
        self.last_served_from = "composite-fallthrough"
        return None

    async def close(self) -> None:
        for child in self._sinks:
            try:
                await child.close()
            except Exception as exc:  # pragma: no cover
                _LOG.warning(
                    "composite child %s.close() raised: %s", type(child).__name__, exc
                )


def _tier_label_for(sink: Any) -> str:
    """Identify the tier a sink represents for the `x-lifecycle-tier` header.

    Honors a `last_served_from` class/instance attribute when present
    (the canonical hook); otherwise falls back to a class-name heuristic.
    """
    label = getattr(sink, "last_served_from", None)
    if label in ("ring-buffer", "sqlite", "external"):
        return str(label)
    cls_name = type(sink).__name__
    if "Ring" in cls_name:
        return "ring-buffer"
    if "Sqlite" in cls_name:
        return "sqlite"
    if "Broadcast" in cls_name:
        # BroadcastingLifecycleSink is write-only; should never serve a query
        # but if it does, label honestly.
        return "external"
    return "external"


__all__ = ["CompositeLifecycleSink"]
