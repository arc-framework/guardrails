"""Verify ``docs/public-surface.md`` against the supported runtime surface.

Three checks:

1. **Supported-entry resolution**: every manifest entry resolves to a real
    runtime attribute on the package.
2. **Stable-kind consistency**: for ``stability_band: stable`` entries, the
    runtime kind matches the recorded kind (best-effort — full shape pinning
    lives in the contract snapshot suite).
3. **Deprecation-shim wiring**: every entry in the manifest's "Renamed"
    table still resolves to the old name and that import emits
    ``DeprecationWarning``.

Exits 0 on all-pass, non-zero with a structured error report on any
failure. The pytest wrappers under
``packages/{core,pip,api}/tests/contract/test_public_surface_manifest.py``
invoke the same logic for local-run convenience.
"""

from __future__ import annotations

import importlib
import inspect
import re
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "docs" / "public-surface.md"

PACKAGES = ("arc_guard_core", "arc_guard", "arc_guard_service")

VALID_BANDS = {"stable", "provisional", "experimental", "internal"}


@dataclass(frozen=True)
class Entry:
    name: str
    kind: str
    stability_band: str
    introduced_in: str
    stabilized_in: str
    notes: str


@dataclass(frozen=True)
class RenameRow:
    old_name: str
    old_module: str
    new_name: str
    new_module: str


def _read_manifest(path: Path) -> tuple[dict[str, list[Entry]], list[RenameRow]]:
    """Parse the manifest into per-package entry lists + rename rows."""
    if not path.is_file():
        raise FileNotFoundError(f"public-surface manifest not found: {path}")
    text = path.read_text(encoding="utf-8")

    blocks_by_package: dict[str, list[Entry]] = {pkg: [] for pkg in PACKAGES}
    pkg_pattern = re.compile(r"^##\s+Package:\s+(\S+)\s*$", re.MULTILINE)
    yaml_pattern = re.compile(r"```yaml\s*\n(.*?)\n```", re.DOTALL)

    pkg_matches = list(pkg_pattern.finditer(text))
    for i, match in enumerate(pkg_matches):
        pkg_name = match.group(1)
        if pkg_name not in PACKAGES:
            continue
        block_start = match.end()
        block_end = pkg_matches[i + 1].start() if i + 1 < len(pkg_matches) else len(text)
        section = text[block_start:block_end]
        for yaml_match in yaml_pattern.finditer(section):
            data = yaml.safe_load(yaml_match.group(1)) or []
            for raw in data:
                blocks_by_package[pkg_name].append(
                    Entry(
                        name=raw["name"],
                        kind=raw["kind"],
                        stability_band=raw["stability_band"],
                        introduced_in=str(raw["introduced_in"]),
                        stabilized_in=str(raw.get("stabilized_in", "TBD")),
                        notes=raw.get("notes", ""),
                    ),
                )

    renames = _read_rename_table(text)
    return blocks_by_package, renames


def _read_rename_table(text: str) -> list[RenameRow]:
    """Parse the 'Renamed (deprecation shims active)' Markdown table."""
    rows: list[RenameRow] = []
    table_match = re.search(
        r"##\s+Renamed.*?\n\|.*?\|\n\|[-\s|]+\|\n((?:\|.*\n)+)",
        text,
        re.DOTALL,
    )
    if not table_match:
        return rows
    body = table_match.group(1)
    for line in body.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        if all(c.startswith("(") for c in cells if c):
            continue
        old_full, new_full = cells[0], cells[1]
        if "." not in old_full or "." not in new_full:
            continue
        old_module, _, old_name = old_full.rpartition(".")
        new_module, _, new_name = new_full.rpartition(".")
        rows.append(RenameRow(old_name=old_name, old_module=old_module, new_name=new_name, new_module=new_module))
    return rows


def _kind_of(obj: Any) -> str:
    """Best-effort kind label matching the manifest schema."""
    if isinstance(obj, type):
        if hasattr(obj, "_value2member_map_"):
            return "enum"
        if hasattr(obj, "__dataclass_fields__"):
            return "dataclass"
        return "class"
    if inspect.isfunction(obj) or inspect.ismethod(obj):
        return "function"
    if isinstance(obj, (str, int, float, bool, dict, tuple, frozenset)):
        return "constant"
    if inspect.ismodule(obj):
        return "module"
    type_name = type(obj).__name__
    if type_name == "_ProtocolMeta":
        return "protocol"
    if type_name == "ModelMetaclass":
        return "class"
    if type_name == "_LiteralGenericAlias":
        return "constant"
    if type_name in {"FidelityScore", "DeceptionScore"}:
        return "constant"
    return "constant"


def check_manifest(path: Path = MANIFEST_PATH) -> list[str]:
    """Return a list of error strings (empty list = all checks passed)."""
    errors: list[str] = []
    try:
        per_pkg, renames = _read_manifest(path)
    except FileNotFoundError as exc:
        return [f"manifest missing: {exc}"]

    for pkg in PACKAGES:
        manifest_entries = per_pkg.get(pkg, [])
        seen_names: set[str] = set()

        for entry in manifest_entries:
            if entry.name in seen_names:
                errors.append(f"[{pkg}] duplicate manifest entry for {entry.name}")
                continue
            seen_names.add(entry.name)
            if entry.stability_band not in VALID_BANDS:
                errors.append(f"[{pkg}] {entry.name}: invalid stability_band {entry.stability_band!r}")
                continue

            obj = _resolve_manifest_entry(pkg, entry, errors)
            if obj is None:
                continue
            if entry.stability_band == "stable":
                _check_stable_kind(pkg, entry, obj, errors)

    for row in renames:
        _check_rename_shim(row, errors)

    return errors


def _resolve_manifest_entry(pkg: str, entry: Entry, errors: list[str]) -> Any | None:
    """Resolve one manifest entry to its runtime object, recording a readable error."""
    try:
        module = importlib.import_module(pkg)
        return getattr(module, entry.name)
    except Exception as exc:
        errors.append(f"[{pkg}] {entry.name}: manifest entry does not resolve at runtime ({exc})")
        return None


def _check_stable_kind(pkg: str, entry: Entry, obj: Any, errors: list[str]) -> None:
    """Best-effort kind check: declared kind matches runtime kind."""
    runtime_kind = _kind_of(obj)
    declared = entry.kind
    aliases = {"dataclass": {"class", "dataclass"}, "class": {"class", "dataclass"}}
    accepted = aliases.get(declared, {declared})
    if runtime_kind not in accepted:
        errors.append(
            f"[{pkg}] {entry.name}: stable kind drift — manifest says {declared!r}, runtime is {runtime_kind!r}",
        )


def _check_rename_shim(row: RenameRow, errors: list[str]) -> None:
    """Verify the rename row's old name still resolves and emits DeprecationWarning."""
    try:
        old_module = importlib.import_module(row.old_module)
    except Exception as exc:
        errors.append(f"rename [{row.old_module}.{row.old_name} → ...]: cannot import old module ({exc})")
        return
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        try:
            getattr(old_module, row.old_name)
        except Exception as exc:
            errors.append(f"rename [{row.old_module}.{row.old_name} → ...]: shim missing ({exc})")
            return
    deprecation_messages = [str(w.message) for w in captured if issubclass(w.category, DeprecationWarning)]
    if not deprecation_messages:
        errors.append(f"rename [{row.old_module}.{row.old_name} → ...]: shim did not emit DeprecationWarning")
        return
    if not any(row.new_name in msg for msg in deprecation_messages):
        errors.append(
            f"rename [{row.old_module}.{row.old_name} → ...]: DeprecationWarning does not name {row.new_name}",
        )


def main(argv: list[str] | None = None) -> int:
    errors = check_manifest()
    if not errors:
        print("public-surface manifest: OK")
        return 0
    sys.stderr.write("public-surface manifest drift detected:\n")
    for err in errors:
        sys.stderr.write(f"  - {err}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
