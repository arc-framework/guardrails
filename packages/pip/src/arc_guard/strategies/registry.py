"""StrategyRegistry — name-to-strategy lookup.

Module-level singleton backed by ``FrozenAfterConstructionRegistry``.
Built-in strategies register themselves on import of
``arc_guard.strategies``. User strategies register via
``register_strategy(name, strategy)`` or the ``@strategy("name")``
decorator. Once the pipeline is constructed and ``freeze_strategies()``
runs, further ``register_strategy`` calls raise
``RegistryFrozenError``.

Policy-load validation consults this registry — unknown names raise
``ConfigCrossFieldError``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from arc_guard_core._registry_lock import FrozenAfterConstructionRegistry
from arc_guard_core.exceptions import StrategyError

_REGISTRY: FrozenAfterConstructionRegistry[Any] = FrozenAfterConstructionRegistry()

T = TypeVar("T")


def register_strategy(name: str, strategy: Any) -> None:
    """Register a strategy by name.

    Raises:
        ValueError: when ``name`` is empty.
        StrategyError: when ``name`` is already registered to a
            different instance. Duplicate registration with the same
            instance is a no-op.
        RegistryFrozenError: when called after ``freeze_strategies()``.
    """
    if not name:
        raise ValueError("strategy name must be non-empty")
    existing = _REGISTRY.get(name)
    if existing is not None and existing is not strategy:
        raise StrategyError(
            f"strategy {name!r} already registered to a different instance",
            code="strategy.failed",
            details={"name": name},
        )
    _REGISTRY.register(name, strategy, replace=True)


def get_strategy(name: str) -> Any:
    """Resolve a registered strategy by name.

    Raises:
        StrategyError: when ``name`` is not registered.
    """
    strat = _REGISTRY.get(name)
    if strat is None:
        raise StrategyError(
            f"strategy {name!r} is not registered",
            code="strategy.failed",
            details={"name": name},
        )
    return strat


def is_registered(name: str) -> bool:
    """Return True if ``name`` is registered."""
    return name in _REGISTRY


def list_registered() -> frozenset[str]:
    """Return all registered names (snapshot)."""
    return frozenset(_REGISTRY.names())


def freeze_strategies() -> None:
    """Seal the registry. Called from pipeline construction so
    post-construction registration attempts raise
    ``RegistryFrozenError``.
    """
    _REGISTRY.freeze()


def is_strategies_frozen() -> bool:
    return _REGISTRY.is_frozen


def strategy(name: str) -> Callable[[type[T]], type[T]]:
    """Decorator form: ``@strategy("my_name")`` registers an instance."""

    def _wrap(cls: type[T]) -> type[T]:
        try:
            instance = cls()
        except TypeError:
            # Class needs constructor args; the user must register manually.
            return cls
        register_strategy(name, instance)
        return cls

    return _wrap


def _reset_for_testing() -> None:
    """Test-only: unfreeze the registry while preserving import-time
    built-in registrations. Production code MUST NOT call this.
    """
    _REGISTRY._unfreeze_for_testing()


__all__ = [
    "register_strategy",
    "get_strategy",
    "is_registered",
    "list_registered",
    "freeze_strategies",
    "is_strategies_frozen",
    "strategy",
]
