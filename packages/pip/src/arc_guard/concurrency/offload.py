"""Async offload helper for blocking work.

The async pipeline path must not block the event loop on inspector or
strategy work that uses synchronous primitives (model inference, large
regex, etc.). ``run_off_loop`` delegates to ``asyncio.to_thread`` so
the call runs on the default thread-pool executor; an
``arc_guardrails.observability.offload`` counter increments per
invocation so operators can audit how often the offload path fires.

Concurrency: thread-safe via the asyncio event loop's default executor
(threading.Lock managed by the executor itself; callers do not need
to lock).
Failure mode: raises whatever the wrapped callable raised. The
counter increment fires before the call so a raised exception still
shows up in the offload count.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

from arc_guard_core.observability import MetricSink

OFFLOAD_COUNTER = "arc_guardrails.observability.offload"

T = TypeVar("T")


async def run_off_loop(
    func: Callable[..., T],
    *args: Any,
    stage: str,
    metric_sink: MetricSink,
    **kwargs: Any,
) -> T:
    """Run ``func`` on the asyncio default thread-pool executor.

    Args:
        func: Synchronous callable to invoke.
        *args, **kwargs: Forwarded to ``func``.
        stage: Stage label attached to the offload counter so operators
            can break down offloads by pipeline stage.
        metric_sink: Counter sink; the offload increment fires before
            the call.

    Returns:
        Whatever ``func`` returned.
    """
    metric_sink.counter(OFFLOAD_COUNTER, attributes={"stage": stage})
    return await asyncio.to_thread(func, *args, **kwargs)


__all__ = ["run_off_loop", "OFFLOAD_COUNTER"]
