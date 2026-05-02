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


class FidelityThresholds(BaseModel):
    """Operator-tunable fidelity threshold tuple.

    The three values gate the fidelity-driven action ladder:

    - ``score >= warn`` — informational only.
    - ``clarify <= score < warn`` — set ``GuardResult.fidelity_warning = True``.
    - ``refuse <= score < clarify`` — populate ``GuardResult.clarification``.
    - ``score < refuse`` — populate ``GuardResult.refusal`` and block.

    Defaults (0.7, 0.5, 0.3) are illustrative — operators tune for their
    deployment's measured drift profile.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    warn: float = Field(default=0.7, ge=0.0, le=1.0)
    clarify: float = Field(default=0.5, ge=0.0, le=1.0)
    refuse: float = Field(default=0.3, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _ordered(self) -> FidelityThresholds:
        if not (self.warn > self.clarify > self.refuse):
            raise ValueError(
                f"FidelityThresholds requires warn > clarify > refuse; "
                f"got warn={self.warn}, clarify={self.clarify}, refuse={self.refuse}"
            )
        return self


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
    fidelity_thresholds: FidelityThresholds = Field(default_factory=FidelityThresholds)

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
    "FidelityThresholds",
    "ObservabilityConfig",
]
