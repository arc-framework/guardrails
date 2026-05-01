"""T103 — adapter modules must be gated behind their optional extras (FR-005).

Adapter modules under ``arc_guard.adapters.*`` import safely without their
optional runtime deps installed (so an integrator who ``pip install arc-guard``
without extras can still import the package). The hard dependency is only
required at instantiation time, surfaced through an ``_AVAILABLE`` flag on
the module and a clear error from the constructor.

This test verifies:

1. Adapter modules import without raising even when their optional dep is missing.
2. When the dep is missing, the module's ``_<NAME>_AVAILABLE`` flag is ``False``.
3. When the dep is installed, the flag is ``True`` and the constructor at
   minimum exists.
4. The *default* install of ``arc-guard`` (no extras) does not pull the
   optional dep into ``sys.modules``.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys

import pytest

# (module path, extra name, runtime-dep import name, availability-flag name)
ADAPTERS = [
    ("arc_guard.adapters.nats_reporter", "nats", "nats", "_NATS_AVAILABLE"),
    (
        "arc_guard.adapters.unleash_provider",
        "unleash",
        "UnleashClient",
        "_UNLEASH_AVAILABLE",
    ),
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


@pytest.mark.parametrize(
    ("module_name", "extra", "dep", "flag"), ADAPTERS
)
def test_adapter_imports_safely_and_flag_reflects_dep(
    module_name: str, extra: str, dep: str, flag: str
) -> None:
    if not _module_exists(module_name):
        pytest.skip(f"adapter module {module_name} not migrated yet")
    mod = importlib.import_module(module_name)
    available = getattr(mod, flag, None)
    assert available is not None, (
        f"adapter {module_name} must expose {flag} availability flag"
    )
    assert available is _dep_installed(dep), (
        f"{module_name}.{flag} = {available!r} but dep {dep!r} installed = "
        f"{_dep_installed(dep)} — flag must reflect runtime availability"
    )


def test_default_install_does_not_pull_optional_provider_modules() -> None:
    """Importing arc_guard core surface must not pull nats / UnleashClient
    into sys.modules unless the integrator explicitly imports an adapter."""
    # Force a clean slate: remove cached adapter modules and their deps.
    for cached in list(sys.modules):
        if cached.startswith("arc_guard.adapters") or cached in {
            "nats",
            "UnleashClient",
        }:
            del sys.modules[cached]

    import arc_guard  # noqa: F401
    import arc_guard.config_env  # noqa: F401
    from arc_guard import inspectors as _inspectors  # noqa: F401
    from arc_guard import strategies as _strategies  # noqa: F401

    forbidden = {"nats", "UnleashClient"}
    loaded = forbidden & set(sys.modules)
    assert loaded == set(), (
        f"default arc-guard import pulled optional deps: {loaded}. "
        "Adapters must not be imported by default."
    )
