"""Deprecation shim — ``arc_guard.registry`` moved to ``arc_guard_core.registry``."""

from __future__ import annotations

from arc_guard._shim import make_submodule_getattr

__getattr__ = make_submodule_getattr(
    submodule="arc_guard.registry",
    new_module="arc_guard_core.registry",
)
