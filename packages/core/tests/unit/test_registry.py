"""Unit tests for EntityRegistry, including a concurrent-registration smoke test."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from arc_guard_core.registry import EntityRegistry
from arc_guard_core.types import EntityDefinition


def test_register_and_iterate() -> None:
    reg = EntityRegistry()
    reg.register(EntityDefinition(name="EMAIL", category="PII"))
    reg.register(EntityDefinition(name="CARD", category="PCI"))
    names = [e.name for e in reg.entities()]
    assert names == ["EMAIL", "CARD"]


def test_concurrent_registration_no_lost_updates() -> None:
    """Thread-safety must be exercised by a concurrent test."""
    reg = EntityRegistry()
    n = 200

    def add(i: int) -> None:
        reg.register(EntityDefinition(name=f"E{i}", category="CUSTOM"))

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(add, range(n)))

    snapshot = list(reg.entities())
    assert len(snapshot) == n
    assert {e.name for e in snapshot} == {f"E{i}" for i in range(n)}


def test_entities_returns_a_snapshot() -> None:
    reg = EntityRegistry()
    reg.register(EntityDefinition(name="X", category="CUSTOM"))
    snap_before = list(reg.entities())
    reg.register(EntityDefinition(name="Y", category="CUSTOM"))
    assert len(snap_before) == 1  # unchanged
    assert len(list(reg.entities())) == 2
