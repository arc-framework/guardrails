"""arc-guard — batteries-included guardrails library.

historical import paths are kept alive through a PEP 562 ``__getattr__`` shim
that consults ``_legacy.LEGACY_SYMBOLS``. Each access of a deprecated name
emits a ``DeprecationWarning`` naming the replacement and removal version.

See ``_legacy.py`` for the deprecation table and the migration note URL.
"""

from __future__ import annotations

import importlib
import warnings
from typing import Any

from arc_guard._legacy import (
    LEGACY_SYMBOLS,
    deprecation_message,
    is_removed,
    removal_message,
)

__version__ = "0.8.0"


def __getattr__(name: str) -> Any:
    entry = LEGACY_SYMBOLS.get(name)
    if entry is None:
        raise AttributeError(f"module 'arc_guard' has no attribute {name!r}")
    if is_removed(entry):
        raise ImportError(removal_message(name, entry))
    warnings.warn(
        deprecation_message(name, entry),
        DeprecationWarning,
        stacklevel=2,
    )
    module = importlib.import_module(entry.new_module)
    return getattr(module, entry.new_name)


def __dir__() -> list[str]:
    return ["__version__", *LEGACY_SYMBOLS.keys()]
