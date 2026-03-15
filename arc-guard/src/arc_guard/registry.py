"""EntityRegistry — thread-safe registry for custom entity definitions."""

from __future__ import annotations

import re
import threading
from typing import Any

from arc_guard.types import EntityDefinition


class EntityRegistry:
    """Thread-safe registry of custom EntityDefinition objects.

    Satisfies the EntityProvider protocol structurally via get_entities().
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entities: list[EntityDefinition] = []

    def register(self, entity: EntityDefinition) -> None:
        """Add an EntityDefinition to the registry."""
        with self._lock:
            self._entities.append(entity)

    def get_entities(self) -> list[EntityDefinition]:
        """Return a snapshot copy of all registered entity definitions."""
        with self._lock:
            return list(self._entities)


_default_registry = EntityRegistry()


def register_entity(
    name: str,
    category: str,
    pattern: re.Pattern[str] | None = None,
    recognizer: Any | None = None,
) -> None:
    """Register a custom entity with the module-level default registry.

    Args:
        name: Unique label, e.g. "AADHAAR", "NZ_IRD".
        category: Broad category: "PII", "PCI", or "CUSTOM".
        pattern: Optional compiled regex for text matching.
        recognizer: Optional presidio PatternRecognizer for richer detection.
    """
    _default_registry.register(
        EntityDefinition(
            name=name,
            category=category,
            pattern=pattern,
            recognizer=recognizer,
        )
    )
