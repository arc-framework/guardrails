"""Deliberate-mutation tests for the diff engine."""

from __future__ import annotations

from copy import deepcopy

from . import _snapshot as snap


def test_added_entry_is_additive() -> None:
    old = [{"name": "A", "kind": "dataclass", "fields": [], "stability": "stable"}]
    new = old + [{"name": "B", "kind": "dataclass", "fields": [], "stability": "stable"}]
    diffs = snap.diff_snapshots(old, new)
    assert any(d.kind == "added" and d.name == "B" for d in diffs)
    assert all(not d.is_breaking() for d in diffs)


def test_removed_entry_is_breaking() -> None:
    old = [{"name": "A", "kind": "dataclass", "fields": [], "stability": "stable"}]
    new: list[dict] = []
    diffs = snap.diff_snapshots(old, new)
    assert any(d.kind == "removed" and d.name == "A" for d in diffs)
    assert all(d.is_breaking() for d in diffs)


def test_renamed_field_is_breaking() -> None:
    old = [
        {
            "name": "M",
            "kind": "dataclass",
            "stability": "stable",
            "fields": [{"name": "old_name", "type": "str", "default": None}],
        }
    ]
    new = deepcopy(old)
    new[0]["fields"] = [{"name": "new_name", "type": "str", "default": None}]
    diffs = snap.diff_snapshots(old, new)
    # Removal + addition; removal is breaking.
    assert any(d.kind == "changed" and "old_name" in d.detail for d in diffs)


def test_type_narrowing_is_breaking() -> None:
    old = [
        {
            "name": "M",
            "kind": "dataclass",
            "stability": "stable",
            "fields": [{"name": "x", "type": "int | str", "default": None}],
        }
    ]
    new = deepcopy(old)
    new[0]["fields"][0]["type"] = "int"
    diffs = snap.diff_snapshots(old, new)
    assert any(
        d.kind == "changed" and "x" in d.detail and "type changed" in d.detail
        for d in diffs
    )


def test_optional_field_added_is_additive() -> None:
    old = [
        {
            "name": "M",
            "kind": "pydantic_model",
            "stability": "stable",
            "fields": [{"name": "x", "type": "int", "required": True, "default": None}],
        }
    ]
    new = deepcopy(old)
    new[0]["fields"].append(
        {"name": "y", "type": "str", "required": False, "default": "'default'"}
    )
    diffs = snap.diff_snapshots(old, new)
    assert any(d.kind == "added" and "y" in d.detail for d in diffs)
    assert all(not d.is_breaking() or "y" not in d.detail for d in diffs)


def test_required_field_added_is_breaking() -> None:
    old = [
        {
            "name": "M",
            "kind": "pydantic_model",
            "stability": "stable",
            "fields": [{"name": "x", "type": "int", "required": True, "default": None}],
        }
    ]
    new = deepcopy(old)
    new[0]["fields"].append(
        {"name": "y", "type": "str", "required": True, "default": None}
    )
    diffs = snap.diff_snapshots(old, new)
    assert any(d.kind == "changed" and "y" in d.detail for d in diffs)


def test_protocol_method_added_is_additive_but_signature_change_is_breaking() -> None:
    old = [
        {
            "name": "P",
            "kind": "protocol",
            "stability": "stable",
            "fields": [],
            "methods": [{"name": "m1", "is_async": False, "params": [], "return": "None"}],
        }
    ]
    new = deepcopy(old)
    new[0]["methods"].append(
        {"name": "m2", "is_async": False, "params": [], "return": "None"}
    )
    diffs = snap.diff_snapshots(old, new)
    assert any(d.kind == "added" and "m2" in d.detail for d in diffs)

    new_again = deepcopy(old)
    new_again[0]["methods"][0]["is_async"] = True
    diffs2 = snap.diff_snapshots(old, new_again)
    assert any(d.kind == "changed" and "m1" in d.detail for d in diffs2)


def test_failure_mode_change_is_breaking() -> None:
    old = [
        {
            "name": "InspectorError",
            "kind": "exception",
            "stability": "stable",
            "fields": [],
            "parent": "PipelineError",
            "failure_mode": "open",
            "valid_codes": [],
        }
    ]
    new = deepcopy(old)
    new[0]["failure_mode"] = "closed"
    diffs = snap.diff_snapshots(old, new)
    assert any(d.kind == "changed" and "failure_mode" in d.detail for d in diffs)


def test_valid_code_added_is_additive_but_removed_is_breaking() -> None:
    old = [
        {
            "name": "InspectorError",
            "kind": "exception",
            "stability": "stable",
            "fields": [],
            "parent": "PipelineError",
            "failure_mode": "open",
            "valid_codes": ["a", "b"],
        }
    ]
    new = deepcopy(old)
    new[0]["valid_codes"] = ["a", "b", "c"]
    diffs = snap.diff_snapshots(old, new)
    assert any(d.kind == "added" and "'c'" in d.detail for d in diffs)

    new2 = deepcopy(old)
    new2[0]["valid_codes"] = ["a"]
    diffs2 = snap.diff_snapshots(old, new2)
    assert any(d.kind == "changed" and "'b'" in d.detail for d in diffs2)


def test_stability_lowered_is_breaking() -> None:
    old = [{"name": "X", "kind": "dataclass", "stability": "stable", "fields": []}]
    new = deepcopy(old)
    new[0]["stability"] = "experimental"
    diffs = snap.diff_snapshots(old, new)
    assert any(d.kind == "changed" and "stability" in d.detail for d in diffs)
