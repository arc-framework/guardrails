"""Every leaf exception has a FAIL_RULE entry, and every FAIL_RULE key
has a foundation ``__failure_mode__`` ClassVar.

Reflects over ``arc_guard_core.exceptions``, walks every concrete leaf
subclass (filtering second-level group classes per the existing
``test_failure_modes.py`` discipline), and asserts each appears as a
key in ``FAIL_RULE``. Adding a new leaf without a ``FAIL_RULE`` entry
fails this test. The reverse check (every key has a ``__failure_mode__``
ClassVar) protects the single-source-of-truth invariant: posture is
read from the foundation, never redeclared in the rule table.
"""

from __future__ import annotations

import inspect

from arc_guard_core import exceptions as exc
from arc_guard_core.failure_modes import FAIL_RULE

# Second-level group classes that organize the hierarchy but are never
# raised directly. They have no ``__failure_mode__`` and no ``FAIL_RULE``
# entry; their leaves do.
GROUP_CLASSES: frozenset[str] = frozenset({
    "ArcGuardError",
    "ConfigError",
    "ValidationError",
    "PipelineError",
    "AdapterError",
})


def _concrete_leaves() -> list[type[exc.ArcGuardError]]:
    """Every concrete subclass of ArcGuardError that is not a group class."""
    leaves: list[type[exc.ArcGuardError]] = []
    for _, member in inspect.getmembers(exc, inspect.isclass):
        if not issubclass(member, exc.ArcGuardError):
            continue
        if member is exc.ArcGuardError:
            continue
        if member.__name__ in GROUP_CLASSES:
            continue
        leaves.append(member)
    return leaves


def test_every_leaf_has_a_fail_rule_entry() -> None:
    """Every leaf in ``arc_guard_core.exceptions`` MUST be a FAIL_RULE key."""
    leaves = _concrete_leaves()
    missing = [cls.__name__ for cls in leaves if cls not in FAIL_RULE]
    assert missing == [], (
        f"Leaf exceptions without FAIL_RULE entries: {missing}. "
        "Either add a FAIL_RULE entry in arc_guard_core.failure_modes "
        "or document why the new class is exempt."
    )


def test_every_fail_rule_key_declares_failure_mode() -> None:
    """Every FAIL_RULE key must have a foundation ``__failure_mode__`` ClassVar.

    Posture is read from the ClassVar at lookup time; without it, the
    posture branch in ``stage_runner`` would have nothing to read.
    """
    missing = [
        cls.__name__
        for cls in FAIL_RULE
        if not hasattr(cls, "__failure_mode__")
    ]
    assert missing == [], (
        f"FAIL_RULE keys missing __failure_mode__ ClassVar: {missing}"
    )
