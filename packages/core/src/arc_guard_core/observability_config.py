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


class JailbreakThresholds(BaseModel):
    """Operator-tunable jailbreak threshold tuple.

    **Direction**: higher score = MORE risk → ordered
    ``refuse > clarify > warn``, the INVERSE of
    :class:`FidelityThresholds` (which is higher = better).

    The three values gate the jailbreak-driven action ladder:

    - ``confidence >= refuse`` — populate ``GuardResult.refusal`` with
      ``RefusalCode.JAILBREAK_STRONG`` and ``action="block"``.
    - ``clarify <= confidence < refuse`` — populate
      ``GuardResult.clarification``.
    - ``warn <= confidence < clarify`` — informational warn-class
      indicator on the decision record.
    - ``confidence < warn`` — no fidelity-driven action.

    Defaults ``(refuse=0.8, clarify=0.6, warn=0.4)`` are illustrative
    starting points; operators tune for their deployment's measured
    false-positive / false-negative rates.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    refuse: float = Field(default=0.8, ge=0.0, le=1.0)
    clarify: float = Field(default=0.6, ge=0.0, le=1.0)
    warn: float = Field(default=0.4, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _ordered(self) -> JailbreakThresholds:
        if not (self.refuse > self.clarify > self.warn):
            raise ValueError(
                f"JailbreakThresholds requires refuse > clarify > warn; "
                f"got refuse={self.refuse}, clarify={self.clarify}, warn={self.warn}"
            )
        return self


class DeceptionThresholds(BaseModel):
    """Operator-tunable deception threshold tuple.

    **Direction**: higher score = MORE deception (worse) → ordered
    ``refuse > clarify > warn``, the INVERSE of
    :class:`FidelityThresholds`.

    Defaults ``(refuse=0.7, clarify=0.5, warn=0.3)`` are illustrative
    starting points.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    refuse: float = Field(default=0.7, ge=0.0, le=1.0)
    clarify: float = Field(default=0.5, ge=0.0, le=1.0)
    warn: float = Field(default=0.3, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _ordered(self) -> DeceptionThresholds:
        if not (self.refuse > self.clarify > self.warn):
            raise ValueError(
                f"DeceptionThresholds requires refuse > clarify > warn; "
                f"got refuse={self.refuse}, clarify={self.clarify}, warn={self.warn}"
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
    jailbreak_thresholds: JailbreakThresholds = Field(
        default_factory=JailbreakThresholds,
    )
    deception_thresholds: DeceptionThresholds = Field(
        default_factory=DeceptionThresholds,
    )

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
    "JailbreakThresholds",
    "DeceptionThresholds",
    "ObservabilityConfig",
]
