"""T045 — Exception hierarchy snapshot + failure-mode declarations (FR-022, SC-006)."""

from __future__ import annotations

from arc_guard_core import exceptions as exc

from . import _snapshot as snap


def test_exceptions_match_baseline(update_snapshot: bool) -> None:
    live = snap.build_exceptions_snapshot()

    if update_snapshot or not snap.EXCEPTIONS_PATH.is_file():
        snap.save_snapshot(snap.EXCEPTIONS_PATH, live)
        return

    baseline = snap.load_snapshot(snap.EXCEPTIONS_PATH)
    diffs = snap.diff_snapshots(baseline, live)
    breaking = [d for d in diffs if d.is_breaking()]
    additive = [d for d in diffs if not d.is_breaking()]

    if breaking:
        raise AssertionError(
            "Exception contract violation. Breaking changes:\n"
            + "\n".join(f"  - [{d.kind}] {d.name}: {d.detail}" for d in breaking)
        )

    if additive:
        raise AssertionError(
            "Additive exception changes (CHANGELOG entry required):\n"
            + "\n".join(f"  - [{d.kind}] {d.name}: {d.detail}" for d in additive)
        )


def test_every_leaf_declares_failure_mode() -> None:
    """FR-022 / SC-006: every leaf exception declares ``__failure_mode__``."""
    live = snap.build_exceptions_snapshot()
    leaves = [
        entry
        for entry in live
        if entry["parent"] not in {"Exception", "BaseException", "object"}
        and entry["parent"] != ""
    ]
    missing = [entry["name"] for entry in leaves if entry.get("failure_mode") is None]
    # Second-level group classes (ConfigError, ValidationError, ...) inherit
    # from ArcGuardError but don't declare a failure mode themselves; their
    # leaves do. Filter group classes explicitly.
    group_classes = {
        "ArcGuardError",
        "ConfigError",
        "ValidationError",
        "PipelineError",
        "AdapterError",
    }
    missing = [name for name in missing if name not in group_classes]
    assert missing == [], (
        f"Leaf exceptions missing __failure_mode__: {missing}"
    )


def test_every_leaf_declares_valid_codes() -> None:
    leaves = [
            exc.ConfigSchemaError,
            exc.ConfigCrossFieldError,
            exc.ApiBoundaryValidationError,
            exc.PipelineContractValidationError,
            exc.AdapterBoundaryValidationError,
            exc.InspectorError,
            exc.StrategyError,
            exc.PolicyRouterError,
            exc.ReporterError,
            exc.FlagProviderError,
            exc.EntityProviderError,
            exc.RefusalEnvelopeError,
        ]
    for cls in leaves:
        codes = getattr(cls, "__valid_codes__", frozenset())
        assert codes, f"{cls.__qualname__} must declare non-empty __valid_codes__"
