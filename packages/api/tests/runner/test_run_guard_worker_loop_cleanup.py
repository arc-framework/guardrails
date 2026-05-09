"""The worker-thread loop tears down cleanly when shut down explicitly.

Tests use ``_shutdown_worker_loop()`` to force teardown between cases so
the daemon thread does not bleed into other tests' threading state.
"""

from __future__ import annotations

import asyncio
import threading

import pytest
from arc_guard_core.types import GuardInput

from arc_guard_service import run_guard
from arc_guard_service.runner import _shutdown_worker_loop


@pytest.mark.asyncio
async def test_worker_thread_joins_after_shutdown_helper_runs() -> None:
    assert asyncio.get_running_loop() is not None
    # Trigger lazy worker-loop construction by calling run_guard from a
    # running-loop context.
    run_guard(GuardInput(text="canary"))

    worker_threads = [t for t in threading.enumerate() if t.name == "arc-guard-service-worker-loop"]
    assert len(worker_threads) == 1, (
        f"expected exactly one worker thread, got {len(worker_threads)}"
    )

    _shutdown_worker_loop()

    worker_threads_after = [
        t
        for t in threading.enumerate()
        if t.name == "arc-guard-service-worker-loop" and t.is_alive()
    ]
    assert worker_threads_after == [], "worker thread did not exit after _shutdown_worker_loop()"


@pytest.mark.asyncio
async def test_shutdown_is_idempotent() -> None:
    _shutdown_worker_loop()
    _shutdown_worker_loop()
    run_guard(GuardInput(text="post-shutdown call"))
    _shutdown_worker_loop()
