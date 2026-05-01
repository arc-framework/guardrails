"""StrategyRegistry — name-to-strategy lookup (Spec 003 FR-025–FR-027).

Module-level singleton, thread-safe RLock. Built-in strategies register
themselves on import of ``arc_guard.strategies``. User strategies register
via ``register_strategy(name, strategy)`` or the ``@strategy("name")``
decorator.

Validation at policy-load time (Spec 003 FR-009) consults this registry —
unknown names raise ``ConfigCrossFieldError``.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, TypeVar

from arc_guard_core.exceptions import StrategyError

_LOCK = threading.RLock()
_REGISTRY: dict[str, Any] = {}

T = TypeVar("T")


def register_strategy(name: str, strategy: Any) -> None:
    """Register a strategy by name.

    Raises:
        ValueError: when ``name`` is empty.
        StrategyError: when ``name`` is already registered to a different
            instance. Duplicate registration with the same instance is a
            no-op.
    """
    if not name:
        raise ValueError("strategy name must be non-empty")
    with _LOCK:
        existing = _REGISTRY.get(name)
        if existing is not None and existing is not strategy:
            raise StrategyError(
                f"strategy {name!r} already registered to a different instance",
                code="strategy.failed",
                details={"name": name},
            )
        _REGISTRY[name] = strategy


def get_strategy(name: str) -> Any:
    """Resolve a registered strategy by name.

    Raises:
        StrategyError: when ``name`` is not registered.
    """
    with _LOCK:
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
    with _LOCK:
        return name in _REGISTRY


def list_registered() -> frozenset[str]:
    """Return all registered names (snapshot)."""
    with _LOCK:
        return frozenset(_REGISTRY.keys())


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
    """Test-only: clear the registry. Production code MUST NOT call this."""
    with _LOCK:
        _REGISTRY.clear()


__all__ = [
    "register_strategy",
    "get_strategy",
    "is_registered",
    "list_registered",
    "strategy",
]
