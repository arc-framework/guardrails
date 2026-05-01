"""T062 — every public stage's documented exceptions match the hierarchy (FR-022, SC-006)."""

from __future__ import annotations

from arc_guard_core import exceptions as exc
from arc_guard_core.protocols import (
    ActionStrategy,
    EntityProvider,
    FlagProvider,
    Guard,
    Inspector,
    Middleware,
    Reporter,
)

# Mapping from public stage to (declared exception, expected failure mode).
# This is the table that ``contracts/exceptions.md`` §"Failure-mode table per
# public stage" formalises. Adding a new stage requires adding a row here.
STAGE_FAILURE_MODE = {
    Inspector: (exc.InspectorError, "open"),
    ActionStrategy: (exc.StrategyError, "closed"),
    Reporter: (exc.ReporterError, "open"),
    FlagProvider: (exc.FlagProviderError, "closed-conservative"),
    EntityProvider: (exc.EntityProviderError, "closed"),
}

# Middleware and Guard are aggregate stages: their failures are routed through
# the per-stage exceptions above plus their own AdapterError-rooted family.
AGGREGATE_STAGES = {Guard, Middleware}


def test_each_stage_has_a_documented_exception() -> None:
    for stage, (exc_cls, _mode) in STAGE_FAILURE_MODE.items():
        assert hasattr(exc_cls, "__failure_mode__"), (
            f"{exc_cls.__qualname__} (declared by {stage.__qualname__}) must set __failure_mode__"
        )


def test_each_stage_failure_mode_matches() -> None:
    for stage, (exc_cls, expected_mode) in STAGE_FAILURE_MODE.items():
        assert exc_cls.__failure_mode__ == expected_mode, (
            f"{exc_cls.__qualname__} (declared by {stage.__qualname__}): expected "
            f"{expected_mode!r}, got {exc_cls.__failure_mode__!r}"
        )


def test_aggregate_stages_are_listed() -> None:
    """The Guard and Middleware Protocols are aggregates — they don't carry a
    single failure-mode marker because they delegate to their constituent
    stages. This test simply records that decision so future contributors
    don't add a marker by mistake.
    """
    for stage in AGGREGATE_STAGES:
        # No __failure_mode__ on the Protocol itself (Protocols can't carry
        # ClassVar markers in a structural way). The Protocol's docstring
        # asserts the aggregate behavior.
        assert "Failure mode:" in (stage.__doc__ or ""), (
            f"{stage.__qualname__} docstring must declare its aggregate failure mode"
        )
