"""EntityProvider protocol — source of custom entity definitions."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from arc_guard_core.types import EntityDefinition


@runtime_checkable
class EntityProvider(Protocol):
    """Provides custom ``EntityDefinition`` instances to inspectors.

    Concurrency: sync. Typically called once at startup; some inspectors
    may call repeatedly for hot-reload.
    Thread-safety: thread-safe.

    Declared exceptions: ``EntityProviderError``.

    Failure mode: closed. A missing or broken entity provider is treated
    as a configuration error; the pipeline cannot start.
    """

    def entities(self) -> Iterable[EntityDefinition]: ...
