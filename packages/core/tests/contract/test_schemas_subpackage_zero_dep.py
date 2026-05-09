"""Contract: ``arc_guard_core.schemas`` imports only from stdlib + pydantic.

Walks every module under the ``arc_guard_core.schemas`` subpackage,
parses each via ``ast``, and asserts the set of imported top-level
packages is a subset of ``{"pydantic"} | stdlib``. This complements
the import-linter ``core_zero_dep`` contract — that one operates over
the whole ``arc_guard_core`` namespace; this test narrowly enforces
the new subpackage's provider-neutrality invariant.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import arc_guard_core.schemas as schemas_pkg

# stdlib_module_names is available on Python 3.10+; we only ship 3.11+.
_STDLIB_TOP_LEVEL = set(sys.stdlib_module_names)

# Allowed third-party imports — exactly one (pydantic) per the contract.
_ALLOWED_THIRD_PARTY = {"pydantic"}

# arc_guard_core sibling imports are obviously fine — same package.
_ALLOWED_INTERNAL_PREFIXES = ("arc_guard_core",)


def _walk_modules() -> list[Path]:
    pkg_root = Path(schemas_pkg.__file__).parent
    return sorted(p for p in pkg_root.glob("*.py"))


def _top_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                # Relative import — internal.
                continue
            if node.module is None:
                continue
            out.add(node.module.split(".")[0])
    return out


def test_schemas_subpackage_exists_and_has_modules() -> None:
    modules = _walk_modules()
    assert len(modules) >= 4, (
        f"expected at least 4 modules under schemas/; found {len(modules)}"
    )


def test_every_schemas_module_imports_stdlib_or_pydantic_only() -> None:
    violations: list[str] = []
    for path in _walk_modules():
        imports = _top_level_imports(path)
        for name in imports:
            if name in _STDLIB_TOP_LEVEL:
                continue
            if name in _ALLOWED_THIRD_PARTY:
                continue
            if any(name.startswith(p) for p in _ALLOWED_INTERNAL_PREFIXES):
                continue
            violations.append(
                f"{path.name} imports {name!r} which is neither stdlib,"
                f" pydantic, nor arc_guard_core"
            )
    assert violations == [], "\n".join(violations)
