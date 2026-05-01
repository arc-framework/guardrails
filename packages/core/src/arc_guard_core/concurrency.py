"""Concurrency markers used in protocol docstrings and tests.

These are not behaviour — they are typed labels for documenting and asserting
sync/async/thread-safety expectations across the library. The contract test
suite reads them off Protocol docstrings via ``test_protocol_signatures.py``.
"""

from __future__ import annotations

from enum import StrEnum


class ConcurrencyMode(StrEnum):
    SYNC_ONLY = "sync"
    ASYNC_ONLY = "async"
    SYNC_OR_ASYNC = "both"


class ThreadSafety(StrEnum):
    THREAD_SAFE = "thread-safe"
    NOT_THREAD_SAFE = "not-thread-safe"
    SINGLE_INSTANCE_PER_THREAD = "per-thread"


__all__ = ["ConcurrencyMode", "ThreadSafety"]
