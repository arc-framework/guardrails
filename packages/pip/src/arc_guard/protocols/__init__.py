"""Deprecation shim — protocols moved to ``arc_guard_core.protocols``.

Both attribute access (``arc_guard.protocols.Guard``) and submodule paths
(``arc_guard.protocols.guard.Guard``) emit a ``DeprecationWarning`` and
forward to the canonical location. Removed in ``arc-guard 0.3.0``.
"""

from __future__ import annotations

from arc_guard._shim import make_submodule_getattr

__getattr__ = make_submodule_getattr(
    submodule="arc_guard.protocols",
    new_module="arc_guard_core.protocols",
)
