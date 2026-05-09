"""ContentPolicyRegistry — name-to-ContentPolicy lookup.

Module-level singleton backed by ``FrozenAfterConstructionRegistry``.
Built-in or operator-registered policies register themselves through
``register_content_policy(name, policy)`` or the
``@content_policy("name")`` decorator. Once the pipeline is constructed
and ``freeze_content_policies()`` runs, further registrations raise
``RegistryFrozenError``.

Mirrors the strategy / selector registry pattern.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from arc_guard_core._registry_lock import FrozenAfterConstructionRegistry
from arc_guard_core.exceptions import ConfigCrossFieldError

_REGISTRY: FrozenAfterConstructionRegistry[Any] = FrozenAfterConstructionRegistry()

T = TypeVar("T")


def register_content_policy(name: str, policy: Any) -> None:
    """Register a content policy by name.

    Raises:
        ValueError: when ``name`` is empty.
        ConfigCrossFieldError: when ``name`` is already registered to a
            different instance.
        RegistryFrozenError: when called after ``freeze_content_policies()``.
    """
    if not name:
        raise ValueError("content policy name must be non-empty")
    existing = _REGISTRY.get(name)
    if existing is not None and existing is not policy:
        raise ConfigCrossFieldError(
            f"content policy {name!r} already registered to a different instance",
            code="config.cross_field_violation",
            details={"name": name},
        )
    _REGISTRY.register(name, policy, replace=True)


def get_content_policy(name: str) -> Any:
    """Resolve a registered content policy by name."""
    cp = _REGISTRY.get(name)
    if cp is None:
        raise ConfigCrossFieldError(
            f"content policy {name!r} is not registered",
            code="config.cross_field_violation",
            details={"name": name},
        )
    return cp


def is_registered(name: str) -> bool:
    return name in _REGISTRY


def list_registered() -> frozenset[str]:
    return frozenset(_REGISTRY.names())


def freeze_content_policies() -> None:
    _REGISTRY.freeze()


def is_content_policies_frozen() -> bool:
    return _REGISTRY.is_frozen


def content_policy(name: str) -> Callable[[type[T]], type[T]]:
    """Decorator form: ``@content_policy("my_name")`` registers an instance."""

    def _wrap(cls: type[T]) -> type[T]:
        try:
            instance = cls()
        except TypeError:
            return cls
        register_content_policy(name, instance)
        return cls

    return _wrap


def _reset_for_testing() -> None:
    """Test-only: unfreeze and clear the content-policy registry.

    Unlike strategies and selectors, no content policies register at
    import time, so a full clear is the safest reset for tests.
    """
    _REGISTRY._reset_for_testing()


__all__ = [
    "register_content_policy",
    "get_content_policy",
    "is_registered",
    "list_registered",
    "freeze_content_policies",
    "is_content_policies_frozen",
    "content_policy",
]
