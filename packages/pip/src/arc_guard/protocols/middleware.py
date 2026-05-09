"""Deprecation shim for arc_guard.protocols.middleware.

The Protocol moved to arc_guard_core.protocols.middleware. Removed
in arc-guard 0.3.0.
"""

from __future__ import annotations

from arc_guard._shim import make_submodule_getattr

__getattr__ = make_submodule_getattr(  # noqa: N816 — PEP 562 module hook
    submodule="arc_guard.protocols.middleware",
    new_module="arc_guard_core.protocols.middleware",
)
