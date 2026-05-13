"""Every leaf exception has a rule reachable via MRO, and every
FAIL_RULE key has a foundation ``__failure_mode__`` ClassVar.

Reflects over ``arc_guard_core.exceptions``, walks every concrete leaf
subclass (filtering second-level group classes per the existing
``test_failure_modes.py`` discipline), and asserts each resolves to a
non-unknown rule via ``lookup_rule``. Subclasses that inherit their
parent's rule via MRO walking (e.g. ``RegistryFrozenError`` inheriting
the ``ConfigCrossFieldError`` rule) pass without a direct
``FAIL_RULE`` entry. The reverse check (every key has a
``__failure_mode__`` ClassVar) protects the single-source-of-truth
invariant: posture is read from the foundation, never redeclared in
the rule table.
"""

from __future__ import annotations

import inspect

from arc_guard_core import exceptions as exc
from arc_guard_core.failure_modes import FAIL_RULE, FAILURE_UNKNOWN, lookup_rule

# Second-level group classes that organize the hierarchy but are never
# raised directly. They have no ``__failure_mode__`` and no ``FAIL_RULE``
# entry; their leaves do.
GROUP_CLASSES: frozenset[str] = frozenset(
    {
        "ArcGuardError",
        "ConfigError",
        "ValidationError",
        "PipelineError",
        "AdapterError",
    }
)


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


def test_every_leaf_resolves_to_a_known_rule() -> None:
    """Every leaf in ``arc_guard_core.exceptions`` MUST resolve to a
    non-unknown rule via MRO walking.

    Subclasses that inherit a parent's rule (e.g.
    ``RegistryFrozenError`` inheriting ``ConfigCrossFieldError``'s
    config rule) are valid; only leaves that fall through to
    ``UNKNOWN_RULE`` fail the test, since that means the leaf has no
    documented failure-mode contract.
    """
    leaves = _concrete_leaves()
    unknown = [
        cls.__name__ for cls in leaves if lookup_rule(cls)[0].failure_class == FAILURE_UNKNOWN
    ]
    assert unknown == [], (
        f"Leaf exceptions resolving to unknown rule: {unknown}. "
        "Either add a FAIL_RULE entry in arc_guard_core.failure_modes "
        "or subclass an exception that already has one."
    )


def test_every_fail_rule_key_declares_failure_mode() -> None:
    """Every FAIL_RULE key must have a foundation ``__failure_mode__`` ClassVar.

    Posture is read from the ClassVar at lookup time; without it, the
    posture branch in ``stage_runner`` would have nothing to read.
    """
    missing = [cls.__name__ for cls in FAIL_RULE if not hasattr(cls, "__failure_mode__")]
    assert missing == [], f"FAIL_RULE keys missing __failure_mode__ ClassVar: {missing}"
