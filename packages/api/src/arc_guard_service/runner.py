"""Synchronous adapter for ``GuardPipeline.pre_process``.

``run_guard(input)`` lets sync callers (CLI scripts, batch jobs, non-async
web frameworks, REPL sessions, Jupyter cells) invoke the guard pipeline
without writing ``asyncio.run(...)`` boilerplate.

Dispatch:

- No running loop in this thread → ``asyncio.run(pipeline.pre_process(input))``.
- Running loop in this thread → submits the coroutine to a module-private
  worker-thread loop via ``asyncio.run_coroutine_threadsafe(...)`` and blocks
  on the resulting ``concurrent.futures.Future``.

The worker-thread loop is constructed lazily under a ``threading.Lock``
guard. Cleanup happens via ``weakref.finalize`` at module GC; tests can call
``_shutdown_worker_loop()`` to force teardown between cases.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
import weakref
from concurrent.futures import Future
from typing import TYPE_CHECKING, Any

from arc_guard_core.types import GuardInput, GuardResult

if TYPE_CHECKING:
    from arc_guard.pipeline import GuardPipeline


_LOCK = threading.Lock()
_WORKER_LOOP: asyncio.AbstractEventLoop | None = None
_WORKER_THREAD: threading.Thread | None = None
_FINALIZER: Any = None  # weakref.finalize generic shape varies across Python versions


def _start_worker_loop() -> tuple[asyncio.AbstractEventLoop, threading.Thread]:
    """Start a fresh asyncio loop on a daemon thread and return both."""
    loop = asyncio.new_event_loop()
    ready = threading.Event()

    def _runner() -> None:
        asyncio.set_event_loop(loop)
        ready.set()
        try:
            loop.run_forever()
        finally:
            with contextlib.suppress(Exception):
                loop.close()

    thread = threading.Thread(
        target=_runner,
        name="arc-guard-service-worker-loop",
        daemon=True,
    )
    thread.start()
    ready.wait()
    return loop, thread


def _ensure_worker_loop() -> asyncio.AbstractEventLoop:
    """Return the module-private worker-thread loop, starting it if needed."""
    global _WORKER_LOOP, _WORKER_THREAD, _FINALIZER
    with _LOCK:
        if _WORKER_LOOP is not None and _WORKER_LOOP.is_running():
            return _WORKER_LOOP
        loop, thread = _start_worker_loop()
        _WORKER_LOOP = loop
        _WORKER_THREAD = thread
        _FINALIZER = weakref.finalize(_module_anchor, _shutdown_worker_loop)
        return loop


def _shutdown_worker_loop() -> None:
    """Stop the worker loop and join its thread. Idempotent."""
    global _WORKER_LOOP, _WORKER_THREAD, _FINALIZER
    with _LOCK:
        loop = _WORKER_LOOP
        thread = _WORKER_THREAD
        finalizer = _FINALIZER
        _WORKER_LOOP = None
        _WORKER_THREAD = None
        _FINALIZER = None
    if loop is not None and loop.is_running():
        loop.call_soon_threadsafe(loop.stop)
    if thread is not None:
        thread.join(timeout=5.0)
    if finalizer is not None:
        finalizer.detach()


class _ModuleAnchor:
    """Weak-referenceable anchor for the module-GC finalizer."""

    __slots__ = ("__weakref__",)


_module_anchor = _ModuleAnchor()


def run_guard(
    input: GuardInput,
    *,
    pipeline: GuardPipeline | None = None,
) -> GuardResult:
    """Run ``pipeline.pre_process(input)`` from a synchronous call site.

    When ``pipeline=None``, constructs the default ``GuardPipeline()`` with
    no overrides.

    Detects an existing running loop and uses a worker-thread loop in that
    case; otherwise calls ``asyncio.run(...)``. Exceptions raised by the
    pipeline propagate as the same exception type — this function never
    wraps them.
    """
    if pipeline is None:
        from arc_guard.pipeline import GuardPipeline as _GP  # noqa: N814

        pipeline = _GP()

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(pipeline.pre_process(input))

    loop = _ensure_worker_loop()
    future: Future[GuardResult] = asyncio.run_coroutine_threadsafe(
        pipeline.pre_process(input),
        loop,
    )
    return future.result()


__all__ = ["run_guard"]
