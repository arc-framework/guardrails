"""Contract snapshot generator and diff (T038-T041).

Walks ``arc_guard_core.__all__`` and produces a JSON snapshot of every public
type's shape (fields, properties, methods, parents, stability markers). The
snapshot is the on-disk reference used by the contract test suite.

Snapshot files live under ``packages/core/tests/contract/snapshots/`` and
are committed to git. Adding a new public symbol is an additive change that
requires a CHANGELOG entry; renaming, removing, or narrowing a public type
fails the contract test.

See ``specs/002-rewrite-foundation/contracts/public-types.md``,
``contracts/protocols.md``, and ``contracts/exceptions.md`` for the diff
rules.
"""

from __future__ import annotations

import dataclasses
import enum
import inspect
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

import arc_guard_core

SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"
PUBLIC_TYPES_PATH = SNAPSHOT_DIR / "public_types.json"
PROTOCOLS_PATH = SNAPSHOT_DIR / "protocols.json"
EXCEPTIONS_PATH = SNAPSHOT_DIR / "exceptions.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _type_repr(annotation: Any) -> str:
    """Stable string representation of a type annotation."""
    if annotation is inspect.Parameter.empty:
        return ""
    if annotation is None:
        return "None"
    if isinstance(annotation, type):
        return annotation.__qualname__
    return str(annotation)


def _is_protocol(obj: Any) -> bool:
    return inspect.isclass(obj) and getattr(obj, "_is_protocol", False)


def _is_pydantic_model(obj: Any) -> bool:
    return inspect.isclass(obj) and issubclass(obj, BaseModel)


def _is_dataclass(obj: Any) -> bool:
    return dataclasses.is_dataclass(obj) and inspect.isclass(obj)


def _is_enum(obj: Any) -> bool:
    return inspect.isclass(obj) and issubclass(obj, enum.Enum)


def _is_exception(obj: Any) -> bool:
    return inspect.isclass(obj) and issubclass(obj, BaseException)


def _stability_for(name: str) -> str:
    """Stability marker — heuristic until explicit @stable annotations land.

    The observability hook protocols (Tracer, Logger, MetricSink and their
    Null counterparts) are experimental until Spec 004 closes; everything
    else is stable.
    """
    experimental = {
        "Tracer",
        "Logger",
        "MetricSink",
        "NullTracer",
        "NullLogger",
        "NullMetricSink",
    }
    if name in experimental:
        return "experimental"
    return "stable"


# ---------------------------------------------------------------------------
# Per-kind introspection
# ---------------------------------------------------------------------------


def _enum_entry(name: str, obj: type[enum.Enum]) -> dict[str, Any]:
    return {
        "name": name,
        "kind": "enum",
        "module": obj.__module__,
        "stability": _stability_for(name),
        "base": obj.__base__.__qualname__ if obj.__base__ else "",
        "values": [
            {"name": member.name, "value": member.value} for member in obj
        ],
    }


def _dataclass_entry(name: str, obj: type) -> dict[str, Any]:
    fields = []
    for field in dataclasses.fields(obj):
        default: Any
        if field.default is not dataclasses.MISSING:
            default = repr(field.default)
        elif field.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
            default = f"<factory:{field.default_factory.__qualname__}>"  # type: ignore[union-attr]
        else:
            default = None
        fields.append(
            {"name": field.name, "type": _type_repr(field.type), "default": default}
        )
    properties = sorted(
        n for n, v in inspect.getmembers(obj, lambda x: isinstance(x, property))
    )
    return {
        "name": name,
        "kind": "dataclass",
        "module": obj.__module__,
        "stability": _stability_for(name),
        "frozen": getattr(obj, "__dataclass_params__", None)
        and obj.__dataclass_params__.frozen
        or False,
        "fields": fields,
        "properties": properties,
    }


def _pydantic_entry(name: str, obj: type[BaseModel]) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
    for fname, finfo in obj.model_fields.items():
        fields.append(
            {
                "name": fname,
                "type": _type_repr(finfo.annotation),
                "required": finfo.is_required(),
                "default": (
                    "<factory>" if finfo.default_factory is not None else repr(finfo.default)
                )
                if not finfo.is_required()
                else None,
            }
        )
    cfg = obj.model_config
    return {
        "name": name,
        "kind": "pydantic_model",
        "module": obj.__module__,
        "stability": _stability_for(name),
        "frozen": bool(cfg.get("frozen", False)),
        "extra": cfg.get("extra", "ignore"),
        "fields": fields,
    }


def _protocol_entry(name: str, obj: type) -> dict[str, Any]:
    methods: list[dict[str, Any]] = []
    for member_name, member in inspect.getmembers(obj):
        if member_name.startswith("_"):
            continue
        if not callable(member):
            continue
        try:
            sig = inspect.signature(member)
        except (TypeError, ValueError):
            continue
        params = []
        for p in sig.parameters.values():
            if p.name == "self":
                continue
            params.append(
                {
                    "name": p.name,
                    "kind": p.kind.name,
                    "annotation": _type_repr(p.annotation),
                    "default": (
                        "<empty>"
                        if p.default is inspect.Parameter.empty
                        else repr(p.default)
                    ),
                }
            )
        methods.append(
            {
                "name": member_name,
                "is_async": inspect.iscoroutinefunction(member),
                "params": params,
                "return": _type_repr(sig.return_annotation),
            }
        )
    methods.sort(key=lambda m: m["name"])
    doc = inspect.getdoc(obj) or ""
    return {
        "name": name,
        "kind": "protocol",
        "module": obj.__module__,
        "stability": _stability_for(name),
        "methods": methods,
        # Concurrency: the contract test (T044) asserts this line exists.
        "has_concurrency_line": "Concurrency:" in doc,
        "has_failure_mode_line": "Failure mode:" in doc,
        "has_thread_safety_line": "Thread-safety:" in doc,
    }


def _exception_entry(name: str, obj: type[BaseException]) -> dict[str, Any]:
    parent = obj.__bases__[0] if obj.__bases__ else None
    return {
        "name": name,
        "kind": "exception",
        "module": obj.__module__,
        "parent": parent.__qualname__ if parent else "",
        "stability": _stability_for(name),
        "failure_mode": getattr(obj, "__failure_mode__", None),
        "valid_codes": sorted(getattr(obj, "__valid_codes__", set())),
    }


def _class_entry(name: str, obj: type) -> dict[str, Any]:
    """Catch-all for non-protocol, non-dataclass, non-pydantic, non-enum classes."""
    methods = []
    for member_name, member in inspect.getmembers(obj, inspect.isfunction):
        if member_name.startswith("_") and member_name not in {"__init__"}:
            continue
        try:
            sig = inspect.signature(member)
        except (TypeError, ValueError):
            continue
        methods.append({"name": member_name, "signature": str(sig)})
    methods.sort(key=lambda m: m["name"])
    return {
        "name": name,
        "kind": "class",
        "module": obj.__module__,
        "stability": _stability_for(name),
        "bases": [b.__qualname__ for b in obj.__bases__],
        "methods": methods,
    }


def _function_entry(name: str, obj: Any) -> dict[str, Any]:
    sig = inspect.signature(obj)
    return {
        "name": name,
        "kind": "function",
        "module": obj.__module__,
        "stability": _stability_for(name),
        "signature": str(sig),
    }


# ---------------------------------------------------------------------------
# Snapshot builders
# ---------------------------------------------------------------------------


def build_public_types_snapshot() -> list[dict[str, Any]]:
    """Walk ``arc_guard_core.__all__`` and emit non-protocol public entries.

    Protocols and exceptions are emitted by their dedicated builders so the
    diffs are categorized.
    """
    out: list[dict[str, Any]] = []
    for name in arc_guard_core.__all__:
        if name == "__version__":
            continue
        obj = getattr(arc_guard_core, name)
        if _is_protocol(obj):
            continue
        if _is_exception(obj):
            continue
        if name == "FailureMode":
            # Literal alias from typing — nothing structural to snapshot.
            out.append(
                {
                    "name": name,
                    "kind": "type_alias",
                    "module": "arc_guard_core.exceptions",
                    "stability": "stable",
                    "alias": str(obj),
                }
            )
            continue
        if _is_enum(obj):
            out.append(_enum_entry(name, obj))
        elif _is_pydantic_model(obj):
            out.append(_pydantic_entry(name, obj))
        elif _is_dataclass(obj):
            out.append(_dataclass_entry(name, obj))
        elif inspect.isclass(obj):
            out.append(_class_entry(name, obj))
        elif callable(obj):
            out.append(_function_entry(name, obj))
        else:
            out.append({"name": name, "kind": "unknown", "stability": "stable"})
    out.sort(key=lambda e: e["name"])
    return out


def build_protocols_snapshot() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in arc_guard_core.__all__:
        obj = getattr(arc_guard_core, name)
        if _is_protocol(obj):
            out.append(_protocol_entry(name, obj))
    out.sort(key=lambda e: e["name"])
    return out


def build_exceptions_snapshot() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in arc_guard_core.__all__:
        obj = getattr(arc_guard_core, name)
        if _is_exception(obj):
            out.append(_exception_entry(name, obj))
    out.sort(key=lambda e: e["name"])
    return out


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Diff:
    kind: str   # "added" | "removed" | "changed"
    name: str
    detail: str

    def is_breaking(self) -> bool:
        return self.kind in {"removed", "changed"}


def diff_snapshots(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[Diff]:
    """Compute structural diff between two snapshot lists.

    Returns a list of ``Diff`` instances. Additive changes (new entries,
    new optional fields) are ``kind="added"``. Anything else is breaking.
    """
    diffs: list[Diff] = []
    old_by_name = {entry["name"]: entry for entry in old}
    new_by_name = {entry["name"]: entry for entry in new}

    for name in sorted(set(old_by_name) - set(new_by_name)):
        diffs.append(Diff("removed", name, f"public symbol {name!r} removed"))

    for name in sorted(set(new_by_name) - set(old_by_name)):
        diffs.append(Diff("added", name, f"public symbol {name!r} added"))

    for name in sorted(set(old_by_name) & set(new_by_name)):
        old_entry = old_by_name[name]
        new_entry = new_by_name[name]
        if old_entry == new_entry:
            continue
        # Stability lowering is breaking
        if old_entry.get("stability") == "stable" and new_entry.get("stability") != "stable":
            diffs.append(Diff("changed", name, "stability lowered from stable"))
        # Field-level diffs (dataclass / pydantic)
        old_fields = {f["name"]: f for f in old_entry.get("fields", [])}
        new_fields = {f["name"]: f for f in new_entry.get("fields", [])}
        for fname in sorted(set(old_fields) - set(new_fields)):
            diffs.append(Diff("changed", name, f"field {fname!r} removed"))
        for fname in sorted(set(new_fields) - set(old_fields)):
            new_required = new_fields[fname].get("required", False) is True
            new_has_default = new_fields[fname].get("default") not in (None, "<empty>")
            additive = (not new_required) or new_has_default
            kind = "added" if additive else "changed"
            diffs.append(Diff(kind, name, f"field {fname!r} added"))
        for fname in sorted(set(old_fields) & set(new_fields)):
            of, nf = old_fields[fname], new_fields[fname]
            if of.get("type") != nf.get("type"):
                diffs.append(
                    Diff(
                        "changed",
                        name,
                        f"field {fname!r} type changed: {of.get('type')!r} -> {nf.get('type')!r}",
                    )
                )
            if of.get("default") != nf.get("default"):
                diffs.append(
                    Diff(
                        "changed",
                        name,
                        (
                            f"field {fname!r} default changed: "
                            f"{of.get('default')!r} -> {nf.get('default')!r}"
                        ),
                    )
                )
        # Protocol method diffs
        old_methods = {m["name"]: m for m in old_entry.get("methods", []) if isinstance(m, dict)}
        new_methods = {m["name"]: m for m in new_entry.get("methods", []) if isinstance(m, dict)}
        for mname in sorted(set(old_methods) - set(new_methods)):
            diffs.append(Diff("changed", name, f"method {mname!r} removed"))
        for mname in sorted(set(new_methods) - set(old_methods)):
            diffs.append(Diff("added", name, f"method {mname!r} added"))
        for mname in sorted(set(old_methods) & set(new_methods)):
            om, nm = old_methods[mname], new_methods[mname]
            if om != nm:
                diffs.append(
                    Diff("changed", name, f"method {mname!r} signature changed")
                )
        # Exception failure-mode change is always breaking.
        if old_entry.get("failure_mode") != new_entry.get("failure_mode"):
            diffs.append(
                Diff(
                    "changed",
                    name,
                    f"failure_mode changed: {old_entry.get('failure_mode')!r} -> "
                    f"{new_entry.get('failure_mode')!r}",
                )
            )
        # Exception valid_codes — additive ok, removal breaking
        old_codes = set(old_entry.get("valid_codes", []))
        new_codes = set(new_entry.get("valid_codes", []))
        for code in sorted(old_codes - new_codes):
            diffs.append(Diff("changed", name, f"valid_code {code!r} removed"))
        for code in sorted(new_codes - old_codes):
            diffs.append(Diff("added", name, f"valid_code {code!r} added"))
    return diffs


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def load_snapshot(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return json.loads(path.read_text())


def save_snapshot(path: Path, data: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def update_snapshot_flag() -> bool:
    """Return True if the user passed ``--update-snapshot`` on the pytest CLI."""
    import sys

    return "--update-snapshot" in sys.argv
