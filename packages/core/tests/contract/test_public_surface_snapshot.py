"""T043 — public-types snapshot test."""

from __future__ import annotations

from . import _snapshot as snap


def test_public_surface_matches_baseline(update_snapshot: bool) -> None:
    live = snap.build_public_types_snapshot()

    if update_snapshot or not snap.PUBLIC_TYPES_PATH.is_file():
        snap.save_snapshot(snap.PUBLIC_TYPES_PATH, live)
        return

    baseline = snap.load_snapshot(snap.PUBLIC_TYPES_PATH)
    diffs = snap.diff_snapshots(baseline, live)
    breaking = [d for d in diffs if d.is_breaking()]
    additive = [d for d in diffs if not d.is_breaking()]

    if breaking:
        msg_lines = [
            "Public-surface contract violation. Breaking changes detected:",
            *(f"  - [{d.kind}] {d.name}: {d.detail}" for d in breaking),
            "",
            "These require the deprecation flow (see contracts/deprecation-policy.md).",
            "If intentional and additive, run:  pytest -k snapshot --update-snapshot",
        ]
        raise AssertionError("\n".join(msg_lines))

    if additive:
        # Additive changes are allowed but require a CHANGELOG note.
        # The CI gate that pairs with this test should enforce CHANGELOG diff;
        # here we only report.
        msg_lines = [
            "Additive public-surface changes detected (require CHANGELOG entry):",
            *(f"  - [{d.kind}] {d.name}: {d.detail}" for d in additive),
            "",
            "Re-run with --update-snapshot once the CHANGELOG is updated.",
        ]
        raise AssertionError("\n".join(msg_lines))
