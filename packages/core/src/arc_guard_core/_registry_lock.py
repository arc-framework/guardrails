"""Frozen-after-construction registry helper.

Internal core helper used by ``EntityRegistry`` (core-resident) and the
pip-resident ``StrategyRegistry``. Both registries follow the same
discipline: thread-safe registration during startup, then ``freeze()``
seals the registry; subsequent reads take a ``MappingProxyType``
snapshot that does not require locking on the hot path.

Concurrency model:

- ``register(name, value)`` acquires an ``RLock`` and inserts into the
  underlying dict. Re-registration of the same name uses the same lock
  so concurrent registrations do not race.
- ``freeze()`` flips a flag (also under the lock). After freeze, any
  ``register(...)`` raises ``RegistryFrozenError``.
- ``snapshot()`` returns a read-only ``MappingProxyType`` view of a
  shallow-copied dict. Readers never block on the lock.

Underscore prefix marks this as a shared internal helper; it is not
part of ``arc_guard_core``'s public surface.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from types import MappingProxyType
from typing import Generic, TypeVar

from arc_guard_core.exceptions import RegistryFrozenError

T = TypeVar("T")


class FrozenAfterConstructionRegistry(Generic[T]):
    """Mixin / wrapper providing frozen-after-construction discipline.

    Subclass this directly or compose by holding an instance. The class
    is generic over the value type so concrete registries can declare
    their value shape (``ActionStrategy``, ``EntityDefinition``, …).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._items: dict[str, T] = {}
        self._frozen = False

    def register(self, name: str, value: T, *, replace: bool = False) -> None:
        """Insert ``value`` under ``name``.

        Raises ``RegistryFrozenError`` after ``freeze()``. With
        ``replace=False`` (the default), re-registering the same name
        without explicitly opting in is a silent no-op so importing
        the same module twice does not race; callers that need
        replace-on-conflict semantics pass ``replace=True``.
        """
        with self._lock:
            if self._frozen:
                raise RegistryFrozenError(
                    f"cannot register {name!r}: registry is frozen",
                    code="registry.frozen",
                    details={"name": name},
                )
            if not replace and name in self._items:
                return
            self._items[name] = value

    def freeze(self) -> None:
        """Seal the registry. Idempotent; calling on an already-frozen
        registry is a no-op.
        """
        with self._lock:
            self._frozen = True

    @property
    def is_frozen(self) -> bool:
        with self._lock:
            return self._frozen

    def snapshot(self) -> Mapping[str, T]:
        """Return a read-only snapshot for the hot path.

        The snapshot is a ``MappingProxyType`` over a shallow-copied
        dict, so post-snapshot mutations of the registry do not bleed
        into already-issued snapshots.
        """
        with self._lock:
            view: Mapping[str, T] = MappingProxyType(dict(self._items))
        return view

    def get(self, name: str) -> T | None:
        with self._lock:
            return self._items.get(name)

    def names(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._items.keys())

    def __contains__(self, name: object) -> bool:
        if not isinstance(name, str):
            return False
        with self._lock:
            return name in self._items

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def _reset_for_testing(self) -> None:
        """Test-only: unfreeze and clear. Production code MUST NOT call this."""
        with self._lock:
            self._items.clear()
            self._frozen = False

    def _unfreeze_for_testing(self) -> None:
        """Test-only: unfreeze without clearing. Use to keep import-time
        registrations intact across freeze/unfreeze cycles in tests.
        """
        with self._lock:
            self._frozen = False


__all__ = ["FrozenAfterConstructionRegistry"]
