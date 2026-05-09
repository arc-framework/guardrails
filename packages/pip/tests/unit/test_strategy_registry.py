"""StrategyRegistry tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from arc_guard_core.exceptions import StrategyError

# Importing this package triggers built-in registration.
import arc_guard.strategies  # noqa: F401
from arc_guard.strategies.registry import (
    get_strategy,
    is_registered,
    list_registered,
    register_strategy,
    strategy,
)


def test_built_ins_registered() -> None:
    for name in ("redact", "hash", "block", "warn", "tokenize"):
        assert is_registered(name), f"{name} should be a built-in"


def test_get_strategy_returns_registered_instance() -> None:
    s = get_strategy("redact")
    assert s.name == "redact"


def test_unknown_name_raises() -> None:
    with pytest.raises(StrategyError):
        get_strategy("does_not_exist")


def test_empty_name_rejected() -> None:
    with pytest.raises(ValueError):
        register_strategy("", object())


def test_duplicate_same_instance_is_noop() -> None:
    s = get_strategy("redact")
    # Registering the same instance again must not raise.
    register_strategy("redact", s)


def test_duplicate_different_instance_raises() -> None:
    class FakeRedact:
        name = "redact"

    with pytest.raises(StrategyError):
        register_strategy("redact", FakeRedact())


def test_decorator_registers() -> None:
    @strategy("test_decorator")
    class TestStrategy:
        name = "test_decorator"

    assert is_registered("test_decorator")
    assert get_strategy("test_decorator").name == "test_decorator"


def test_concurrent_registration() -> None:
    """Registry is thread-safe."""

    def register(i: int) -> None:
        class S:
            name = f"concurrent_{i}"

        register_strategy(f"concurrent_{i}", S())

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(register, range(50)))

    snapshot = list_registered()
    for i in range(50):
        assert f"concurrent_{i}" in snapshot
