"""FlagProvider protocol — runtime behavioural knobs."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from arc_guard_core.types import GuardContext


@runtime_checkable
class FlagProvider(Protocol):
    """Runtime feature-flag interface.

    Concurrency: sync. Implementations may cache, but the cache must be
    safe to share across threads.
    Thread-safety: thread-safe.

    Declared exceptions: ``FlagProviderError``.

    Failure mode: closed-conservative. On error, ``is_enabled`` MUST return
    ``False`` so the pipeline takes the safer default. This contract is
    documented and enforced by the test suite.
    """

    def is_enabled(self, name: str, *, context: GuardContext | None = None) -> bool: ...
