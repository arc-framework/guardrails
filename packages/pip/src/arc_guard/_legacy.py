"""Spec 001 -> Spec 002 deprecation table.

Every entry maps an old ``arc_guard.*`` import path to its new home in
``arc_guard_core``. Imports of the old paths emit a ``DeprecationWarning``
naming the replacement and the removal version.

The table is the single source of truth for the deprecation flow. The
contract test suite under ``tests/deprecation/`` asserts every entry is
reachable through the PEP 562 ``__getattr__`` shim.

See specs/002-rewrite-foundation/contracts/deprecation-policy.university.
"""

from __future__ import annotations

from dataclasses import dataclass

MIGRATION_NOTE_URL = (
    "https://example.invalid/arc-guardrails/docs/walkthrough/"
    "002-rewrite-foundation.university#migration"
)


@dataclass(frozen=True)
class LegacyEntry:
    """One row in the deprecation table."""

    new_module: str
    new_name: str
    removed_in: str
    note_url: str = MIGRATION_NOTE_URL


# Mapping of old `arc_guard.*` attribute -> new home.
# The key is the attribute name accessed on `arc_guard` (or the relevant submodule).
LEGACY_SYMBOLS: dict[str, LegacyEntry] = {
    # Types
    "RiskLevel": LegacyEntry("arc_guard_core.types", "RiskLevel", "0.3.0"),
    "GuardContext": LegacyEntry("arc_guard_core.types", "GuardContext", "0.3.0"),
    "GuardInput": LegacyEntry("arc_guard_core.types", "GuardInput", "0.3.0"),
    "Finding": LegacyEntry("arc_guard_core.types", "Finding", "0.3.0"),
    "GuardResult": LegacyEntry("arc_guard_core.types", "GuardResult", "0.3.0"),
    "EntityDefinition": LegacyEntry("arc_guard_core.types", "EntityDefinition", "0.3.0"),
    # Config — Spec 001 GuardConfig (presidio + model fields) preserved unchanged
    # under arc_guard.config_env. Spec 002's generic contract is a new class at
    # arc_guard_core.config.GuardConfig with a different shape; callers that
    # want the new contract must opt in to the new path.
    "GuardConfig": LegacyEntry("arc_guard.config_env", "GuardConfig", "0.3.0"),
    # Registry
    "EntityRegistry": LegacyEntry("arc_guard_core.registry", "EntityRegistry", "0.3.0"),
    "register_entity": LegacyEntry("arc_guard_core.registry", "register_entity", "0.3.0"),
    # Protocols
    "Guard": LegacyEntry("arc_guard_core.protocols.guard", "Guard", "0.3.0"),
    "Inspector": LegacyEntry("arc_guard_core.protocols.inspector", "Inspector", "0.3.0"),
    "ActionStrategy": LegacyEntry("arc_guard_core.protocols.strategy", "ActionStrategy", "0.3.0"),
    "Reporter": LegacyEntry("arc_guard_core.protocols.reporter", "Reporter", "0.3.0"),
    "FlagProvider": LegacyEntry(
        "arc_guard_core.protocols.flag_provider", "FlagProvider", "0.3.0"
    ),
    "Middleware": LegacyEntry(
        "arc_guard_core.protocols.middleware", "Middleware", "0.3.0"
    ),
    "EntityProvider": LegacyEntry(
        "arc_guard_core.protocols.entity_provider", "EntityProvider", "0.3.0"
    ),
}

# The current arc-guard release version. The shim raises ImportError when
# CURRENT_VERSION >= entry.removed_in. This version is updated by the release
# process, not by callers.
CURRENT_VERSION = "0.2.0"


def _version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split(".") if part.isdigit())


def is_removed(entry: LegacyEntry) -> bool:
    return _version_tuple(CURRENT_VERSION) >= _version_tuple(entry.removed_in)


def deprecation_message(name: str, entry: LegacyEntry) -> str:
    return (
        f"arc_guard.{name} moved to {entry.new_module}.{entry.new_name}. "
        f"The old import path is removed in arc-guard {entry.removed_in}. "
        f"See {entry.note_url}"
    )


def removal_message(name: str, entry: LegacyEntry) -> str:
    return (
        f"arc_guard.{name} was removed in arc-guard {entry.removed_in}. "
        f"Import {entry.new_name} from {entry.new_module} instead. "
        f"See {entry.note_url}"
    )


__all__ = [
    "LegacyEntry",
    "LEGACY_SYMBOLS",
    "CURRENT_VERSION",
    "MIGRATION_NOTE_URL",
    "is_removed",
    "deprecation_message",
    "removal_message",
]
