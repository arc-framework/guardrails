"""SelectorRegistry — name-to-StrategySelector lookup.

Module-level singleton backed by ``FrozenAfterConstructionRegistry``.
Built-in selectors (e.g. ``DefaultStrategySelector``) register themselves
on import of ``arc_guard.selectors``. User selectors register via
``register_selector(name, selector)`` or the ``@selector("name")``
decorator. Once the pipeline is constructed and ``freeze_selectors()``
runs, further ``register_selector`` calls raise ``RegistryFrozenError``.

Policy-load validation consults this registry — unknown names raise
``ConfigCrossFieldError`` (mirrors the strategy registry pattern).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from arc_guard_core._registry_lock import FrozenAfterConstructionRegistry
from arc_guard_core.exceptions import StrategyError

_REGISTRY: FrozenAfterConstructionRegistry[Any] = FrozenAfterConstructionRegistry()

T = TypeVar("T")


def register_selector(name: str, selector: Any) -> None:
    """Register a selector by name.

    Raises:
        ValueError: when ``name`` is empty.
        StrategyError: when ``name`` is already registered to a
            different instance. Duplicate registration with the same
            instance is a no-op.
        RegistryFrozenError: when called after ``freeze_selectors()``.
    """
    if not name:
        raise ValueError("selector name must be non-empty")
    existing = _REGISTRY.get(name)
    if existing is not None and existing is not selector:
        raise StrategyError(
            f"selector {name!r} already registered to a different instance",
            code="selector.failed",
            details={"name": name},
        )
    _REGISTRY.register(name, selector, replace=True)


def get_selector(name: str) -> Any:
    """Resolve a registered selector by name.

    Raises:
        StrategyError: when ``name`` is not registered.
    """
    sel = _REGISTRY.get(name)
    if sel is None:
        raise StrategyError(
            f"selector {name!r} is not registered",
            code="selector.failed",
            details={"name": name},
        )
    return sel


def is_registered(name: str) -> bool:
    """Return True if ``name`` is registered."""
    return name in _REGISTRY


def list_registered() -> frozenset[str]:
    """Return all registered names (snapshot)."""
    return frozenset(_REGISTRY.names())


def freeze_selectors() -> None:
    """Seal the registry. Called from pipeline construction so
    post-construction registration attempts raise ``RegistryFrozenError``.
    """
    _REGISTRY.freeze()


def is_selectors_frozen() -> bool:
    return _REGISTRY.is_frozen


def selector(name: str) -> Callable[[type[T]], type[T]]:
    """Decorator form: ``@selector("my_name")`` registers an instance."""

    def _wrap(cls: type[T]) -> type[T]:
        try:
            instance = cls()  # type: ignore[call-arg]
        except TypeError:
            return cls
        register_selector(name, instance)
        return cls

    return _wrap


def _reset_for_testing() -> None:
    """Test-only: unfreeze the registry while preserving import-time
    built-in registrations. Production code MUST NOT call this.
    """
    _REGISTRY._unfreeze_for_testing()


__all__ = [
    "register_selector",
    "get_selector",
    "is_registered",
    "list_registered",
    "freeze_selectors",
    "is_selectors_frozen",
    "selector",
]
