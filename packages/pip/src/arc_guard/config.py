"""Deprecation shim — Spec 001 ``arc_guard.config`` is split.

The Spec 001 ``GuardConfig`` (presidio / model paths) is preserved unchanged
under ``arc_guard.config_env``. The Spec 002 generic contract lives at
``arc_guard_core.config.GuardConfig`` with a different shape.

This shim redirects ``arc_guard.config.GuardConfig`` to the legacy shape in
``arc_guard.config_env`` so Spec 001 callers see no breaking change. The
shim is removed in ``arc-guard 0.3.0``; callers must update to either
``arc_guard.config_env`` (for the legacy presidio shape) or
``arc_guard_core.config`` (for the new generic contract).
"""

from __future__ import annotations

from arc_guard._shim import make_submodule_getattr

__getattr__ = make_submodule_getattr(
    submodule="arc_guard.config",
    new_module="arc_guard.config_env",
)
