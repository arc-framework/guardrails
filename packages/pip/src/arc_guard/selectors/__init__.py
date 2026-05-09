"""arc_guard.selectors — StrategySelector implementations + registry.

Bundled selectors (e.g. ``DefaultStrategySelector``) auto-register on
import once they exist; this module only re-exports the registry
surface.
"""

from __future__ import annotations

from arc_guard.selectors.default import DefaultStrategySelector
from arc_guard.selectors.registry import (
    freeze_selectors,
    get_selector,
    is_registered,
    is_selectors_frozen,
    list_registered,
    register_selector,
    selector,
)

__all__ = [
    "DefaultStrategySelector",
    "register_selector",
    "get_selector",
    "is_registered",
    "list_registered",
    "freeze_selectors",
    "is_selectors_frozen",
    "selector",
]
