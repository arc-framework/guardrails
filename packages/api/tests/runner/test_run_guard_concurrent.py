"""``run_guard`` is thread-safe under concurrent calls.

Eight worker threads each call ``run_guard`` simultaneously with distinct
inputs. The test asserts every result corresponds to its calling thread's
input — no cross-talk through the worker-thread loop.
"""

from __future__ import annotations

import threading

from arc_guard_core.types import GuardInput

from arc_guard_service import run_guard


def test_eight_threads_each_get_their_own_result() -> None:
    n = 8
    results: dict[int, str] = {}
    barrier = threading.Barrier(n)

    def _call(i: int) -> None:
        barrier.wait()
        result = run_guard(GuardInput(text=f"thread-{i}-input"))
        results[i] = result.text

    threads = [threading.Thread(target=_call, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert len(results) == n
    for i in range(n):
        assert results[i] == f"thread-{i}-input", (
            f"thread {i} got '{results[i]}' instead of 'thread-{i}-input'"
        )
