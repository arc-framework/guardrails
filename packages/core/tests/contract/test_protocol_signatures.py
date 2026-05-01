"""Protocol signature snapshot + concurrency-declaration assertion."""

from __future__ import annotations

from . import _snapshot as snap


def test_protocols_match_baseline(update_snapshot: bool) -> None:
    live = snap.build_protocols_snapshot()

    if update_snapshot or not snap.PROTOCOLS_PATH.is_file():
        snap.save_snapshot(snap.PROTOCOLS_PATH, live)
        return

    baseline = snap.load_snapshot(snap.PROTOCOLS_PATH)
    diffs = snap.diff_snapshots(baseline, live)
    breaking = [d for d in diffs if d.is_breaking()]
    additive = [d for d in diffs if not d.is_breaking()]

    if breaking:
        raise AssertionError(
            "Protocol contract violation. Breaking changes:\n"
            + "\n".join(f"  - [{d.kind}] {d.name}: {d.detail}" for d in breaking)
        )

    if additive:
        raise AssertionError(
            "Additive protocol changes (CHANGELOG entry required):\n"
            + "\n".join(f"  - [{d.kind}] {d.name}: {d.detail}" for d in additive)
        )


def test_every_protocol_declares_concurrency_mode() -> None:
    """every public protocol's docstring must contain a
    ``Concurrency:`` line declaring sync/async/both."""
    live = snap.build_protocols_snapshot()
    missing = [entry["name"] for entry in live if not entry.get("has_concurrency_line")]
    assert missing == [], (
        f"Protocols missing 'Concurrency:' docstring line: {missing}. "
        "Each public protocol must declare sync/async/both."
    )


def test_every_protocol_declares_failure_mode() -> None:
    live = snap.build_protocols_snapshot()
    missing = [entry["name"] for entry in live if not entry.get("has_failure_mode_line")]
    assert missing == [], (
        f"Protocols missing 'Failure mode:' docstring line: {missing}. "
        "Each public protocol must declare its failure mode."
    )
