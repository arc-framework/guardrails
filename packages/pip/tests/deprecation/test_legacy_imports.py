"""Every legacy public symbol is reachable through the shim with a DeprecationWarning."""

from __future__ import annotations

import importlib
import warnings

import pytest

import arc_guard
from arc_guard._legacy import LEGACY_SYMBOLS, deprecation_message


@pytest.mark.parametrize("name", sorted(LEGACY_SYMBOLS.keys()))
def test_legacy_symbol_is_reachable_with_deprecation_warning(name: str) -> None:
    entry = LEGACY_SYMBOLS[name]

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        value = getattr(arc_guard, name)

    assert value is not None
    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(deprecations) == 1, f"expected one DeprecationWarning for arc_guard.{name}"
    msg = str(deprecations[0].message)
    assert entry.new_module in msg
    assert entry.new_name in msg
    assert f"arc-guard {entry.removed_in}" in msg
    assert msg == deprecation_message(name, entry)


@pytest.mark.parametrize("name", sorted(LEGACY_SYMBOLS.keys()))
def test_legacy_symbol_resolves_to_new_home(name: str) -> None:
    entry = LEGACY_SYMBOLS[name]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        actual = getattr(arc_guard, name)
    new_module = importlib.import_module(entry.new_module)
    expected = getattr(new_module, entry.new_name)
    assert actual is expected


def test_unknown_attribute_raises_attribute_error() -> None:
    with pytest.raises(AttributeError):
        _ = arc_guard.does_not_exist  # type: ignore[attr-defined]
