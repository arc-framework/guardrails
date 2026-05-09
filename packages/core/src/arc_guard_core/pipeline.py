"""GuardPipeline shape for arc-guard-core.

This is the contract layer's view of the pipeline: an empty harness that
accepts a ``GuardConfig`` and exposes the four canonical entry points. The
batteries-included implementation (with the inspector chain, policy router,
strategies, and reporters) lives in ``arc_guard.pipeline``.

This pipeline shape only routes around the ``enabled`` flag and runs
the configured inspectors (none, by default in ``core``) — it never imports
adapter or provider code.
"""

from __future__ import annotations

from collections.abc import Sequence

from arc_guard_core.config import GuardConfig
from arc_guard_core.exceptions import PipelineContractValidationError
from arc_guard_core.types import (
    Finding,
    GuardInput,
    GuardResult,
    PolicyDecision,
    RiskLevel,
)


def _validate_finding(finding: Finding) -> None:
    """Raise ``PipelineContractValidationError`` if *finding* is malformed."""
    if finding.start < 0 or finding.end <= finding.start:
        raise PipelineContractValidationError(
            f"Finding has invalid span [{finding.start}:{finding.end}]",
            code="pipeline.invalid_span",
            details={"start": finding.start, "end": finding.end},
        )
    if finding.score is not None and not (0.0 <= finding.score <= 1.0):
        raise PipelineContractValidationError(
            f"Finding has out-of-range score {finding.score!r}",
            code="pipeline.invalid_score",
            details={"score": finding.score},
        )
    if not finding.inspector:
        raise PipelineContractValidationError(
            "Finding is missing inspector name",
            code="pipeline.missing_inspector",
            details={"entity_type": finding.entity_type},
        )
    if not isinstance(finding.risk_level, RiskLevel):
        raise PipelineContractValidationError(
            f"Finding has invalid risk_level {finding.risk_level!r}",
            code="pipeline.invalid_severity",
            details={"risk_level": repr(finding.risk_level)},
        )


def _validate_decision(decision: PolicyDecision) -> None:
    """Raise ``PipelineContractValidationError`` if *decision* is malformed."""
    if not decision.finding_ids:
        raise PipelineContractValidationError(
            "PolicyDecision has empty finding_ids",
            code="pipeline.invalid_decision",
            details={"strategy": decision.strategy},
        )
    if not decision.strategy:
        raise PipelineContractValidationError(
            "PolicyDecision has empty strategy",
            code="pipeline.invalid_decision",
            details={"finding_ids": list(decision.finding_ids)},
        )
    if not decision.rationale:
        raise PipelineContractValidationError(
            "PolicyDecision has empty rationale",
            code="pipeline.invalid_decision",
            details={"strategy": decision.strategy},
        )


class GuardPipeline:
    """Empty pipeline shape from ``arc-guard-core``.

    The pipeline shape supports four entry points (sync + async pre/post)
    and the disabled / pass-through flow. With no inspectors registered, the
    pass-through returns the input text unchanged with ``action="pass"``.

    This class IS the structural ``Guard`` protocol implementation provided
    by ``core``. ``arc_guard.pipeline`` extends it with the inspector chain,
    middleware, strategies, and reporters.
    """

    def __init__(self, *, config: GuardConfig | None = None) -> None:
        self.config = config if config is not None else GuardConfig()

    # -- async entry points ---------------------------------------------------

    async def pre_process(self, guard_input: GuardInput) -> GuardResult:
        return self._run(guard_input, phase="pre_process")

    async def post_process(self, guard_input: GuardInput) -> GuardResult:
        return self._run(guard_input, phase="post_process")

    # -- sync wrappers --------------------------------------------------------

    def pre_process_sync(self, guard_input: GuardInput) -> GuardResult:
        return self._run(guard_input, phase="pre_process")

    def post_process_sync(self, guard_input: GuardInput) -> GuardResult:
        return self._run(guard_input, phase="post_process")

    # -- internal -------------------------------------------------------------

    def _run(
        self,
        guard_input: GuardInput,
        *,
        phase: str,
    ) -> GuardResult:
        if not self.config.enabled:
            return GuardResult(
                text=guard_input.text,
                action="pass",
                bypass_reason="disabled",
                phase=phase,  # type: ignore[arg-type]
            )
        # No inspectors are wired in this contract layer; the implementation
        # chain lives in arc_guard.pipeline.
        return GuardResult(
            text=guard_input.text,
            action="pass",
            phase=phase,  # type: ignore[arg-type]
        )

    # -- helpers exposed for downstream callers ------------------------------

    @staticmethod
    def validate_findings(findings: Sequence[Finding]) -> None:
        for f in findings:
            _validate_finding(f)

    @staticmethod
    def validate_decisions(decisions: Sequence[PolicyDecision]) -> None:
        for d in decisions:
            _validate_decision(d)


# Convenience alias for tests that want to call validators directly.
__all__ = [
    "GuardPipeline",
    "_validate_finding",
    "_validate_decision",
]
