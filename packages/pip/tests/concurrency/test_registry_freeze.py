"""Frozen-after-construction registries: post-freeze register raises.

Both the pip-resident strategy registry and the core-resident entity
registry follow the same discipline. Once frozen, ``register`` raises
``RegistryFrozenError`` (a ``ConfigCrossFieldError`` subclass that
inherits the ``config`` rule via MRO).
"""

from __future__ import annotations

import pytest
from arc_guard_core.exceptions import RegistryFrozenError
from arc_guard_core.registry import EntityRegistry
from arc_guard_core.types import EntityDefinition

from arc_guard.strategies.registry import (
    _reset_for_testing,
    freeze_strategies,
    is_strategies_frozen,
    register_strategy,
)


class _NoopStrategy:
    name = "noop"

    def apply(self, text: str, findings):  # type: ignore[no-untyped-def]
        return text, []


def test_strategy_registry_freeze_blocks_registration() -> None:
    _reset_for_testing()
    register_strategy("freeze-block-test-noop", _NoopStrategy())
    assert is_strategies_frozen() is False

    freeze_strategies()
    assert is_strategies_frozen() is True

    with pytest.raises(RegistryFrozenError) as exc_info:
        register_strategy("freeze-block-test-another", _NoopStrategy())
    assert exc_info.value.code == "registry.frozen"
    _reset_for_testing()


def test_strategy_registry_same_instance_register_pre_freeze_is_idempotent() -> None:
    _reset_for_testing()
    instance = _NoopStrategy()
    register_strategy("idempotent-test-noop", instance)
    register_strategy("idempotent-test-noop", instance)  # same instance — silent no-op
    _reset_for_testing()


def test_entity_registry_freeze_blocks_registration() -> None:
    registry = EntityRegistry()
    registry.register(EntityDefinition(name="EMAIL", category="pii"))
    assert registry.is_frozen is False

    registry.freeze()
    assert registry.is_frozen is True

    with pytest.raises(RegistryFrozenError) as exc_info:
        registry.register(EntityDefinition(name="PHONE", category="pii"))
    assert exc_info.value.code == "registry.frozen"


def test_entity_registry_freeze_is_idempotent() -> None:
    registry = EntityRegistry()
    registry.freeze()
    registry.freeze()  # no error
    assert registry.is_frozen is True


def test_entity_registry_reads_after_freeze_still_work() -> None:
    registry = EntityRegistry()
    registry.register(EntityDefinition(name="EMAIL", category="pii"))
    registry.register(EntityDefinition(name="PHONE", category="pii"))
    registry.freeze()

    entities = list(registry.entities())
    assert len(entities) == 2
    assert {e.name for e in entities} == {"EMAIL", "PHONE"}
