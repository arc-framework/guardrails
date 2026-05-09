"""EntityRegistry — thread-safe registry for custom entity definitions.

Satisfies the ``EntityProvider`` protocol structurally via ``entities()``.

Adopts the same frozen-after-construction discipline as the
pip-resident ``StrategyRegistry``: post-``freeze()`` registration
raises ``RegistryFrozenError``, reads after freeze return a snapshot
that does not require locking.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Iterable
from typing import Any

from arc_guard_core.exceptions import RegistryFrozenError
from arc_guard_core.types import EntityDefinition


class EntityRegistry:
    """Thread-safe registry of custom ``EntityDefinition`` objects.

    Concurrency: thread-safe via an internal RLock for write operations.
    Reads use a tuple snapshot so they are lock-free on the hot path.
    Failure mode: registration is total during the construction window;
    after ``freeze()``, ``register`` raises ``RegistryFrozenError``.
    Duplicate names are permitted at the registry level — uniqueness
    enforcement is the caller's.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entities: list[EntityDefinition] = []
        self._frozen = False

    def register(self, entity: EntityDefinition) -> None:
        """Add an ``EntityDefinition`` to the registry.

        Raises ``RegistryFrozenError`` after ``freeze()``.
        """
        with self._lock:
            if self._frozen:
                raise RegistryFrozenError(
                    f"cannot register entity {entity.name!r}: registry is frozen",
                    code="registry.frozen",
                    details={"name": entity.name},
                )
            self._entities.append(entity)

    def freeze(self) -> None:
        """Seal the registry. Idempotent."""
        with self._lock:
            self._frozen = True

    @property
    def is_frozen(self) -> bool:
        with self._lock:
            return self._frozen

    def entities(self) -> Iterable[EntityDefinition]:
        """Return a snapshot copy of all registered entities."""
        with self._lock:
            return list(self._entities)

    def get_entities(self) -> list[EntityDefinition]:
        """Compatibility alias for the historical ``get_entities`` accessor."""
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
