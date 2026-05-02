"""``run_guard`` works from inside a running asyncio loop.

The pytest-asyncio fixture brings up an event loop before the test body
runs; calling ``run_guard`` here exercises the worker-thread-loop branch
of the two-mode dispatch.
"""

from __future__ import annotations

import asyncio

import pytest
from arc_guard_core.types import GuardInput

from arc_guard_service import run_guard


@pytest.mark.asyncio
async def test_run_guard_under_running_loop_returns_populated_result() -> None:
    assert asyncio.get_running_loop() is not None
    result = run_guard(GuardInput(text="hello from async"))
    assert result is not None
    assert result.action in {"pass", "block", "redact"}


@pytest.mark.asyncio
async def test_run_guard_under_running_loop_does_not_raise_runtime_error() -> None:
    try:
        run_guard(GuardInput(text="async caller path"))
    except RuntimeError as exc:
        if "asyncio.run() cannot be called from a running event loop" in str(exc):
            pytest.fail("run_guard incorrectly called asyncio.run() from a running loop")
        raise
