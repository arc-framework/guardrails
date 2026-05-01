"""Configuration schema for arc-guard-core.

``GuardConfig`` is a frozen pydantic v2 model with ``extra='forbid'`` so
unknown fields fail at load time (FR-016). Environment hydration lives in
``arc_guard.config_env`` (the ``pip`` package); ``core`` does no env IO.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

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
    def _validate_cross_fields(self, info: ValidationInfo | None = None) -> GuardConfig:  # type: ignore[override]
        if not self.enabled:
            return self
        # No registered-name check here; the runtime registry is in `pip`.
        # Cross-field rule: if `lite_mode` is set and `inspector_order` is empty,
        # the pipeline is effectively a no-op — that's allowed but recorded.
        return self


__all__ = ["GuardConfig"]
