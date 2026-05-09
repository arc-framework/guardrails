"""Helper for per-submodule PEP 562 deprecation shims."""

from __future__ import annotations

import importlib
import warnings
from typing import Any

from arc_guard._legacy import CURRENT_VERSION, MIGRATION_NOTE_URL, _version_tuple


def make_submodule_getattr(
    submodule: str,
    new_module: str,
    name_map: dict[str, str] | None = None,
    removed_in: str = "0.3.0",
) -> Any:
    """Build a ``__getattr__`` for a deprecation-shim submodule.

    Args:
        submodule: legacy dotted path, e.g. ``"arc_guard.types"``.
        new_module: canonical module path, e.g. ``"arc_guard_core.types"``.
        name_map: optional explicit attribute -> new name mapping. When
            absent, the lookup uses the same name in the new module.
        removed_in: version that drops the shim.
    """
    name_map = name_map or {}

    def __getattr__(name: str) -> Any:  # noqa: N807 — PEP 562 module-level hook
        target_name = name_map.get(name, name)
        # Only forward if the target actually exists in the new module.
        try:
            target_module = importlib.import_module(new_module)
        except ModuleNotFoundError as e:
            raise AttributeError(
                f"module {submodule!r} cannot resolve {name!r}: "
                f"target module {new_module!r} unavailable ({e})"
            ) from e

        if not hasattr(target_module, target_name):
            raise AttributeError(f"module {submodule!r} has no attribute {name!r}")

        if _version_tuple(CURRENT_VERSION) >= _version_tuple(removed_in):
            raise ImportError(
                f"{submodule}.{name} was removed in arc-guard {removed_in}. "
                f"Import {target_name} from {new_module} instead. "
                f"See {MIGRATION_NOTE_URL}"
            )

        warnings.warn(
            f"{submodule}.{name} moved to {new_module}.{target_name}. "
            f"The old import path is removed in arc-guard {removed_in}. "
            f"See {MIGRATION_NOTE_URL}",
            DeprecationWarning,
            stacklevel=2,
        )
        return getattr(target_module, target_name)

    return __getattr__


__all__ = ["make_submodule_getattr"]
