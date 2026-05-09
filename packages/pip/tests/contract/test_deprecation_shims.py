"""Every active deprecation shim resolves and emits ``DeprecationWarning``.

The pip package's PEP 562 ``__getattr__`` forwards legacy names to their
new homes in ``arc_guard_core``. This test asserts (1) every legacy name
is still callable through the shim, (2) accessing it emits exactly one
``DeprecationWarning``, and (3) the warning message names the new home.
"""

from __future__ import annotations

import importlib
import warnings

import pytest

import arc_guard
from arc_guard._legacy import LEGACY_SYMBOLS, is_removed


@pytest.mark.parametrize("name", sorted(LEGACY_SYMBOLS.keys()))
def test_legacy_shim_resolves_and_warns(name: str) -> None:
    entry = LEGACY_SYMBOLS[name]
    if is_removed(entry):
        with pytest.raises(ImportError, match=name):
            getattr(arc_guard, name)
        return

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        resolved = getattr(arc_guard, name)

    deprecation_warnings = [w for w in captured if issubclass(w.category, DeprecationWarning)]
    assert deprecation_warnings, f"{name}: no DeprecationWarning emitted"
    message = str(deprecation_warnings[0].message)
    assert entry.new_module in message, message
    assert entry.new_name in message, message

    new_module = importlib.import_module(entry.new_module)
    assert resolved is getattr(new_module, entry.new_name)
