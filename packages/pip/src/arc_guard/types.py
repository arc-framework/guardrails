"""Deprecation shim — the historical ``arc_guard.types`` paths now live in
``arc_guard_core.types``. Each access through this module emits a
``DeprecationWarning`` naming the new home; the shim is removed in
``arc-guard 0.3.0``.

See specs/002-rewrite-foundation/contracts/deprecation-policy.university.
"""

from __future__ import annotations

from arc_guard._shim import make_submodule_getattr

__getattr__ = make_submodule_getattr(
    submodule="arc_guard.types",
    new_module="arc_guard_core.types",
)
