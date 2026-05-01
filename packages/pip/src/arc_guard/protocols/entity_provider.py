"""Deprecation shim for arc_guard.protocols.entity_provider.

Spec 002 moves this protocol to arc_guard_core.protocols.entity_provider. Removed
in arc-guard 0.3.0.
"""

from __future__ import annotations

from arc_guard._shim import make_submodule_getattr

__getattr__ = make_submodule_getattr(  # noqa: N816 — PEP 562 module hook
    submodule="arc_guard.protocols.entity_provider",
    new_module="arc_guard_core.protocols.entity_provider",
)
