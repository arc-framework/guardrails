"""Configuration schema for arc-guard-core.

``GuardConfig`` is a frozen pydantic v2 model with ``extra='forbid'`` so
unknown fields fail at load time (FR-016). Environment hydration lives in
``arc_guard.config_env`` (the ``pip`` package); ``core`` does no env IO.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from arc_guard_core.exceptions import ConfigCrossFieldError
from arc_guard_core.observability import (
    Logger,
    MetricSink,
    NullLogger,
    NullMetricSink,
    NullTracer,
    Tracer,
)


class GuardConfig(BaseModel):
    """Structural configuration for the guard pipeline.

    Defaults are deliberately product-neutral (FR-020): no provider names,
    no transport subjects, no platform-specific paths.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    enabled: bool = True
    lite_mode: bool = False
    inspector_order: tuple[str, ...] = Field(default_factory=tuple)
    policy_hints_default: frozenset[str] = Field(default_factory=frozenset)
    tracer: Tracer = Field(default_factory=NullTracer)
    logger: Logger = Field(default_factory=NullLogger)
    metrics: MetricSink = Field(default_factory=NullMetricSink)

    @field_validator("inspector_order", mode="before")
    @classmethod
    def _coerce_order(cls, value: Any) -> Any:
        if isinstance(value, list):
            return tuple(value)
        return value

    @model_validator(mode="after")
    def _validate_cross_fields(self, info: ValidationInfo | None = None) -> GuardConfig:
        if not self.enabled:
            return self
        # Cross-field rule: any name listed in `policy_hints_default` MUST be
        # a non-empty string. Empty strings sneak in via misconfigured env
        # hydration and would silently no-op downstream.
        for hint in self.policy_hints_default:
            if not hint or not isinstance(hint, str):
                raise ConfigCrossFieldError(
                    f"policy_hints_default contains an empty/non-string entry: {hint!r}",
                    code="config.cross_field_violation",
                    details={"field": "policy_hints_default", "value": repr(hint)},
                )
        # Cross-field rule: each entry in `inspector_order` MUST be a
        # non-empty unique string. Duplicates would silently double-run.
        seen: set[str] = set()
        for name in self.inspector_order:
            if not name or not isinstance(name, str):
                raise ConfigCrossFieldError(
                    f"inspector_order contains an empty/non-string entry: {name!r}",
                    code="config.cross_field_violation",
                    details={"field": "inspector_order", "value": repr(name)},
                )
            if name in seen:
                raise ConfigCrossFieldError(
                    f"inspector_order contains duplicate {name!r}",
                    code="config.cross_field_violation",
                    details={"field": "inspector_order", "duplicate": name},
                )
            seen.add(name)
        return self


__all__ = ["GuardConfig"]
