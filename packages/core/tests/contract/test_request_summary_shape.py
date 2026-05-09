"""Contract: ``RequestSummary.stage`` Literal stays in sync with
``arc_guard_core.stages.STAGE_DESCRIPTORS``.

If a future spec adds a stage to ``STAGE_DESCRIPTORS`` without also
extending the ``StageName`` Literal in
``arc_guard_core.schemas.request_summary``, this test fails. That's the
intended drift detector — the public-surface manifest also relies on it.
"""

from __future__ import annotations

from typing import get_args

from arc_guard_core.schemas.request_summary import StageName
from arc_guard_core.stages import STAGE_DESCRIPTORS


def test_stage_literal_matches_stage_descriptors() -> None:
    literal_names = set(get_args(StageName))
    descriptor_names = set(STAGE_DESCRIPTORS)
    assert literal_names == descriptor_names, (
        f"StageName Literal drift detected.\n"
        f"  in Literal but not in STAGE_DESCRIPTORS: {literal_names - descriptor_names}\n"
        f"  in STAGE_DESCRIPTORS but not in Literal: {descriptor_names - literal_names}"
    )


def test_request_summary_required_fields() -> None:
    """Sanity check: the required-field set on ``RequestSummary`` matches
    data-model.md §2.1."""
    from arc_guard_core.schemas.request_summary import RequestSummary

    required = {
        name
        for name, field in RequestSummary.model_fields.items()
        if field.is_required()
    }
    assert required == {"rid", "started_at", "last_event_at", "status", "live"}
