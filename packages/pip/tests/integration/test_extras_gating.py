"""T103 — adapter modules must be gated behind their optional extras (FR-005).

Adapter modules under ``arc_guard.adapters.*`` are scaffolded in Phase 8
(implementation migration). Until the live migration runs, this test is
parametrized over the planned adapter list and asserts the *contract* — when
each adapter module is present, importing it without its extra installed
must raise a ``ModuleNotFoundError`` whose message names the missing extra.

The test discovers `arc_guard.adapters.*` modules at collection time:

- If a module is present *and* its underlying dependency is installed, the
  import should succeed.
- If a module is present and the dependency is missing, the import should
  fail with a clear hint.
- If the module isn't yet migrated to ``packages/pip/`` (Phase 8), the
  test is skipped — there is nothing to gate yet.
"""

from __future__ import annotations

import importlib
import importlib.util

import pytest

# Adapter module path -> required extra name -> required runtime dep.
ADAPTERS = [
    ("arc_guard.adapters.nats_reporter", "nats", "nats"),
    ("arc_guard.adapters.unleash_provider", "unleash", "UnleashClient"),
]


def _module_exists(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ModuleNotFoundError, ValueError):
        return False


def _dep_installed(dep_name: str) -> bool:
    try:
        return importlib.util.find_spec(dep_name) is not None
    except (ModuleNotFoundError, ValueError):
        return False


@pytest.mark.parametrize(("module_name", "extra", "dep"), ADAPTERS)
def test_adapter_module_gated_by_extra(module_name: str, extra: str, dep: str) -> None:
    if not _module_exists(module_name):
        pytest.skip(
            f"adapter module {module_name} not yet migrated to packages/pip "
            f"(Phase 8 — destructive). Test will activate once T076–T087 land."
        )

    if _dep_installed(dep):
        # Both the adapter module and its dep are present; the import must succeed.
        importlib.import_module(module_name)
        return

    # Dep missing — importing the adapter should produce a clear ModuleNotFoundError.
    with pytest.raises(ModuleNotFoundError) as excinfo:
        importlib.import_module(module_name)
    msg = str(excinfo.value).lower()
    assert dep.lower() in msg or extra.lower() in msg, (
        f"adapter {module_name} should hint at the missing dep {dep!r} or extra {extra!r}; "
        f"got: {excinfo.value}"
    )
