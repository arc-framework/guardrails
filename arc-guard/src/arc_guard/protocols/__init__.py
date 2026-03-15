"""Re-exports all 7 arc-guard typing.Protocol interfaces."""

from arc_guard.protocols.entity_provider import EntityProvider
from arc_guard.protocols.flag_provider import FlagProvider
from arc_guard.protocols.guard import Guard
from arc_guard.protocols.inspector import Inspector
from arc_guard.protocols.middleware import Middleware
from arc_guard.protocols.reporter import Reporter
from arc_guard.protocols.strategy import ActionStrategy

__all__ = [
    "Guard",
    "Inspector",
    "ActionStrategy",
    "Reporter",
    "FlagProvider",
    "EntityProvider",
    "Middleware",
]
