from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from arc_guard_core.types import GuardResult

logger = logging.getLogger("arc_guard")

try:
    import nats  # type: ignore[import-not-found]  # noqa: F401

    _NATS_AVAILABLE = True
except ImportError:
    _NATS_AVAILABLE = False


def _result_to_event(result: GuardResult, subject: str) -> dict[str, Any]:
    """Serialise *result* into the canonical guard event schema (v1.0)."""
    return {
        "schema_version": "1.0",
        "phase": result.phase,
        "action": result.action,
        "findings_count": len(result.findings),
        "max_risk": result.max_risk.value,
        "bypass_reason": result.bypass_reason,
        "subject": subject,
    }


class NatsReporter:
    """Publishes GuardResult events to a NATS subject.

    Events are enqueued in a bounded asyncio queue and drained by a background
    task, so ``report()`` returns immediately without waiting for the publish
    to complete.  The reporter never raises from ``report()``.

    Args:
        nc: A connected ``nats.aio.client.Client`` instance.  The type is
            erased to ``Any`` so that importing this class does not require
            ``nats-py`` at import time; the dependency is checked lazily in
            ``__init__``.
        subject: NATS subject to publish events to.
        queue_size: Maximum number of pending events.  Defaults to the
            ``GUARD_REPORTER_QUEUE_SIZE`` environment variable, falling back
            to ``1000``.  When the queue is full the oldest item is dropped.

    Raises:
        ImportError: If ``nats-py`` is not installed.
    """

    def __init__(
        self,
        nc: Any,
        subject: str = "arc.ai.guard.events",
        queue_size: int | None = None,
    ) -> None:
        if not _NATS_AVAILABLE:
            raise ImportError(
                "arc-guard[nats] is required. "
                "Install it with: pip install arc-guard[nats]"
            )
        self._nc = nc
        self._subject = subject

        resolved_size = queue_size if queue_size is not None else int(
            os.environ.get("GUARD_REPORTER_QUEUE_SIZE", "1000")
        )
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=resolved_size)
        self._drain_started: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def report(self, result: GuardResult) -> None:
        """Enqueue *result* for asynchronous publication to NATS.

        Never raises.  If the queue is full, the oldest item is silently
        dropped and a warning is logged.
        """
        try:
            payload = json.dumps(_result_to_event(result, self._subject)).encode()

            if self._queue.full():
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                except asyncio.QueueEmpty:
                    pass
                logger.warning("NatsReporter queue full — dropping oldest event")

            await self._queue.put(payload)

            if not self._drain_started:
                self._drain_started = True
                asyncio.ensure_future(self._drain_loop())
        except Exception as exc:
            logger.warning("arc_guard: NatsReporter.report failed to enqueue: %s", exc)

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> NatsReporter:
        """Enter context — returns self."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit context — waits for all queued events to be published."""
        await self._queue.join()

    async def close(self) -> None:
        """Reporter protocol close — drain pending publishes."""
        await self._queue.join()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _drain_loop(self) -> None:
        """Background task that drains the queue and publishes to NATS."""
        while True:
            payload = await self._queue.get()
            try:
                await self._nc.publish(self._subject, payload)
            except Exception as exc:
                logger.warning("arc_guard: NatsReporter failed to publish: %s", exc)
            finally:
                self._queue.task_done()
