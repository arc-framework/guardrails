"""Re-exports the core Protocol interfaces (8 in total)."""

from __future__ import annotations

from arc_guard_core.protocols.entity_provider import EntityProvider
from arc_guard_core.protocols.flag_provider import FlagProvider
from arc_guard_core.protocols.guard import Guard
from arc_guard_core.protocols.inspector import Inspector
from arc_guard_core.protocols.middleware import Middleware
from arc_guard_core.protocols.policy_router import PolicyRouter
from arc_guard_core.protocols.reporter import Reporter
from arc_guard_core.protocols.strategy import ActionStrategy

__all__ = [
    "Guard",
    "Inspector",
    "ActionStrategy",
    "Reporter",
    "FlagProvider",
    "Middleware",
    "EntityProvider",
    "PolicyRouter",
]
