"""EntityProvider protocol — source of custom entity definitions."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from arc_guard.types import EntityDefinition


@runtime_checkable
class EntityProvider(Protocol):
    """Provides custom EntityDefinitions to the CustomInspector.

    Implementations must be thread-safe — the CustomInspector reads from
    the provider on every inspect() call (hot-reloadable, no caching).
    """

    def get_entities(self) -> list[EntityDefinition]:
        """Return all currently registered entity definitions."""
        ...
