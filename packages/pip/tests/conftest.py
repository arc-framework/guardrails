"""Shared pytest hooks for optional-extra test gating.

The default pip test environment intentionally does not install every
optional extra. Tests that exercise those extras declare a marker and
are skipped at collection time when the backing dependency is absent.
"""

from __future__ import annotations

import importlib.util

import pytest

_OPTIONAL_MARKERS: dict[str, tuple[str, ...]] = {
    "requires_semantic": ("sentence_transformers", "numpy"),
    "requires_code_injection": ("sqlparse",),
}


def _missing_modules(modules: tuple[str, ...]) -> tuple[str, ...]:
    missing: list[str] = []
    for module_name in modules:
        try:
            if importlib.util.find_spec(module_name) is None:
                missing.append(module_name)
        except (ImportError, AttributeError, ValueError):
            missing.append(module_name)
    return tuple(missing)


def _skip_reason(missing: tuple[str, ...]) -> str:
    if len(missing) == 1:
        module_name = missing[0]
        return f"could not import '{module_name}': No module named '{module_name}'"
    rendered = ", ".join(f"'{module_name}'" for module_name in missing)
    return f"could not import required optional dependencies: {rendered}"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    del config
    missing_by_marker = {
        marker_name: _missing_modules(modules) for marker_name, modules in _OPTIONAL_MARKERS.items()
    }
    for item in items:
        for marker_name, missing in missing_by_marker.items():
            if missing and marker_name in item.keywords:
                item.add_marker(pytest.mark.skip(reason=_skip_reason(missing)))
