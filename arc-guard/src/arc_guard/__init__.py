"""arc-guard: General-purpose Python guardrails library.

Public surface:
    from arc_guard import GuardPipeline, GuardInput, GuardContext, GuardResult, GuardConfig
"""

from arc_guard.config import GuardConfig
from arc_guard.pipeline import GuardPipeline
from arc_guard.registry import EntityRegistry, register_entity
from arc_guard.types import (
    EntityDefinition,
    Finding,
    GuardContext,
    GuardInput,
    GuardResult,
    RiskLevel,
)

__version__ = "0.1.0"

__all__ = [
    "GuardConfig",
    "GuardInput",
    "GuardContext",
    "GuardResult",
    "Finding",
    "RiskLevel",
    "EntityDefinition",
    "GuardPipeline",
    "EntityRegistry",
    "register_entity",
]
