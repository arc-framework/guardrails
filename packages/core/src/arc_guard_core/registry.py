"""EntityRegistry — thread-safe registry for custom entity definitions.

Satisfies the ``EntityProvider`` protocol structurally via ``entities()``.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Iterable
from typing import Any

from arc_guard_core.types import EntityDefinition


class EntityRegistry:
    """Thread-safe registry of custom ``EntityDefinition`` objects.

    Concurrency: thread-safe via an internal RLock.
    Failure mode: registration is total (always succeeds); duplicate names are
    permitted at the registry level — uniqueness enforcement is the caller's.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entities: list[EntityDefinition] = []

    def register(self, entity: EntityDefinition) -> None:
        """Add an EntityDefinition to the registry."""
        with self._lock:
            self._entities.append(entity)

    def entities(self) -> Iterable[EntityDefinition]:
        """Return a snapshot copy of all registered entities."""
        with self._lock:
            return list(self._entities)

    # Spec 001 compatibility alias; preserved through deprecation window.
    def get_entities(self) -> list[EntityDefinition]:
        return list(self.entities())


_default_registry = EntityRegistry()


def register_entity(
    name: str,
    category: str,
    pattern: re.Pattern[str] | None = None,
    recognizer: Any | None = None,
) -> None:
    """Register a custom entity with the module-level default registry."""
    _default_registry.register(
        EntityDefinition(
            name=name,
            category=category,
            pattern=pattern,
            recognizer=recognizer,
        )
    )


__all__ = ["EntityRegistry", "register_entity"]
