"""Policy and routing types for arc-guard-core.

These models describe the structural contract of a policy: rules, thresholds,
risk bands, and the routed outcome that a ``PolicyRouter`` returns. The
implementations live in ``arc_guard.policy`` (the pip package).

All types here are part of the public contract and snapshotted by the
contract test suite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from arc_guard_core.exceptions import ConfigCrossFieldError
from arc_guard_core.types import ClarificationRequest, PolicyDecision, RefusalEnvelope, RiskLevel


class RiskBand(StrEnum):
    """Aggregate risk band for one pipeline run.

    Distinct from ``RiskLevel`` (per-finding severity).
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskThresholds(BaseModel):
    """Aggregation thresholds for the risk classifier.

    Defaults are part of the public contract.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    low_max_count: int = 2
    medium_max_count: int = 4
    high_escalates_at: int = 1
    critical_escalates_at: int = 1
    soft_pii_aggregation: int = 3
    min_inspectors_for_critical: int = 1

    @field_validator(
        "low_max_count",
        "medium_max_count",
        "high_escalates_at",
        "critical_escalates_at",
        "soft_pii_aggregation",
    )
    @classmethod
    def _non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("threshold counts must be >= 0")
        return value

    @field_validator("min_inspectors_for_critical")
    @classmethod
    def _at_least_one(cls, value: int) -> int:
        if value < 1:
            raise ValueError("min_inspectors_for_critical must be >= 1")
        return value

    @model_validator(mode="after")
    def _ordered_thresholds(self) -> RiskThresholds:
        if self.low_max_count > self.medium_max_count:
            raise ValueError("low_max_count must be <= medium_max_count")
        return self


class PolicyRule(BaseModel):
    """One routing decision pattern.

    Exactly one of ``strategy`` (legacy: explicit strategy name) or
    ``selector`` (new in 0.8.0: name of a registered ``StrategySelector`` that
    chooses the strategy per finding at runtime) MUST be set. Setting both,
    or neither, raises a configuration error at model construction.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    match: str
    strategy: str | None = None
    selector: str | None = None
    severity_floor: RiskLevel = RiskLevel.LOW
    rationale_template: str = ""
    refusal_human_message: str | None = None
    refusal_next_steps: tuple[str, ...] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", "match")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("PolicyRule id / match must be non-empty")
        return value

    @field_validator("strategy", "selector")
    @classmethod
    def _non_empty_when_set(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("PolicyRule strategy / selector must be non-empty when set")
        return value

    @model_validator(mode="after")
    def _exactly_one_of_strategy_or_selector(self) -> PolicyRule:
        if self.strategy is None and self.selector is None:
            raise ValueError(
                f"PolicyRule {self.id!r}: exactly one of `strategy` or "
                f"`selector` must be set; both are unset"
            )
        if self.strategy is not None and self.selector is not None:
            raise ValueError(
                f"PolicyRule {self.id!r}: `strategy` and `selector` are "
                f"mutually exclusive; both are set "
                f"(strategy={self.strategy!r}, selector={self.selector!r})"
            )
        return self


class PolicyRuleSet(BaseModel):
    """Ordered collection of policy rules plus risk thresholds and clarification config."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rules: tuple[PolicyRule, ...] = Field(default_factory=tuple)
    risk_thresholds: RiskThresholds = Field(default_factory=RiskThresholds)
    clarification_enabled: bool = False
    ambiguous_threshold: RiskBand = RiskBand.MEDIUM
    default_action_when_no_rules_fire: Literal["pass", "block"] = "pass"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate(self) -> PolicyRuleSet:
        if not self.rules and self.default_action_when_no_rules_fire == "block":
            raise ConfigCrossFieldError(
                "PolicyRuleSet has no rules but default_action_when_no_rules_fire='block'",
                code="config.cross_field_violation",
                details={"field": "rules"},
            )
        if self.clarification_enabled and self.ambiguous_threshold == RiskBand.CRITICAL:
            raise ConfigCrossFieldError(
                "ambiguous_threshold cannot be CRITICAL when clarification_enabled=True",
                code="config.cross_field_violation",
                details={"field": "ambiguous_threshold"},
            )
        ids: set[str] = set()
        for rule in self.rules:
            if rule.id in ids:
                raise ConfigCrossFieldError(
                    f"duplicate PolicyRule.id {rule.id!r}",
                    code="config.cross_field_violation",
                    details={"field": "rules", "duplicate": rule.id},
                )
            ids.add(rule.id)
        return self


@dataclass(frozen=True)
class TransformSummary:
    """Summary of one strategy application — used in DecisionRecord."""

    strategy: str
    target_finding_index: int
    before_length: int
    after_length: int
    replacement_kind: Literal["placeholder", "hash", "token", "removed", "warn", "passed"]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RoutedOutcome:
    """What ``PolicyRouter.route`` returns."""

    transformed_text: str
    decisions: tuple[PolicyDecision, ...]
    aggregate_action: Literal["pass", "redact", "hash", "block", "tokenize"]
    aggregate_band: RiskBand
    refusal: RefusalEnvelope | None = None
    clarification: ClarificationRequest | None = None
    fired_rule_ids: tuple[str, ...] = ()
    transforms: tuple[TransformSummary, ...] = ()


__all__ = [
    "RiskBand",
    "RiskThresholds",
    "PolicyRule",
    "PolicyRuleSet",
    "TransformSummary",
    "RoutedOutcome",
]
