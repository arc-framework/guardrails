"""Operator-tunable observability knobs.

Frozen pydantic model hung off ``GuardConfig.observability``. Defaults
are correct for a low-volume security-boundary deployment; operators at
higher volume tune the knobs at construction time. Construction-time
validation means a bad config fails the pipeline construction call, not
the first-request call.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

LogLevelFloor = Literal["debug", "info", "warn", "error"]

_DEFAULT_METRIC_ATTRIBUTE_ALLOW_LIST: frozenset[str] = frozenset({
    "correlation_id",
    "decision_id",
    "stage",
    "action",
    "risk_band",
    "failure_class",
})

_REQUIRED_METRIC_ATTRIBUTES: frozenset[str] = frozenset({
    "correlation_id",
    "stage",
})


class ObservabilityConfig(BaseModel):
    """Per-pipeline observability knobs.

    Validates fully at construction time. Immutable thereafter — share
    the same instance across concurrent runs without synchronization.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    sampling_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    refusal_always_emits: bool = True
    log_level_floor: LogLevelFloor = "info"
    metric_attribute_allow_list: frozenset[str] = Field(
        default=_DEFAULT_METRIC_ATTRIBUTE_ALLOW_LIST,
    )
    max_attribute_bytes: int = Field(default=1024, ge=64)

    @model_validator(mode="after")
    def _validate_required_metric_attributes(self) -> ObservabilityConfig:
        missing = _REQUIRED_METRIC_ATTRIBUTES - self.metric_attribute_allow_list
        if missing:
            raise ValueError(
                "metric_attribute_allow_list must contain at least "
                f"{sorted(_REQUIRED_METRIC_ATTRIBUTES)}; missing {sorted(missing)}"
            )
        return self


__all__ = [
    "LogLevelFloor",
    "ObservabilityConfig",
]
