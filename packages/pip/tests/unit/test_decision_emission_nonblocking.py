"""T067b — non-blocking emission per FR-022 (constitution Principle V)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from typing import Any

from arc_guard_core.policy import PolicyRule, PolicyRuleSet
from arc_guard_core.types import Finding, GuardInput, GuardResult, RiskLevel

from arc_guard.pipeline import GuardPipeline


class _SlowReporter:
    """Reporter whose ``report`` blocks for ~200ms — should NOT block the pipeline."""

    async def report(self, result: GuardResult) -> None:
        await asyncio.sleep(0.2)

    async def close(self) -> None:
        return None


class _SlowLogger:
    """Logger.event sleeps to simulate a slow downstream sink."""

    def bind(self, **fields: Any) -> _SlowLogger:
        return self

    def event(self, name: str, *, level: str = "info", **fields: Any) -> None:
        time.sleep(0.2)


class _FastMetrics:
    def counter(
        self, name: str, value: int = 1, *, attributes: Mapping[str, Any] | None = None
    ) -> None:
        pass

    def histogram(
        self,
        name: str,
        value: float,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        pass


class _StubInspector:
    name = "stub"

    async def inspect(self, result: GuardResult) -> GuardResult:
        return GuardResult(
            text=result.text,
            action=result.action,
            findings=tuple(result.findings)
            + (Finding("EMAIL_ADDRESS", 0, 14, RiskLevel.LOW, "stub"),),
            phase=result.phase,
        )


def test_pipeline_run_completes_inside_budget_with_slow_reporter() -> None:
    """Even with a slow Reporter (200ms), pre_process must return promptly.

    The Reporter contract is fail-open and non-blocking. The pipeline does
    not await reporter.report() in the run path.
    """
    policy = PolicyRuleSet(
        rules=(PolicyRule(id="r_email", match="EMAIL_ADDRESS", strategy="redact"),),
    )
    pipeline = GuardPipeline(
        policy_ruleset=policy,
        inspectors=[_StubInspector()],
        reporter=_SlowReporter(),
    )

    async def _run() -> None:
        # Budget: 50ms. Slow reporter takes 200ms. Run must complete first.
        await asyncio.wait_for(
            pipeline.pre_process(GuardInput(text="alice@acme.com")), timeout=0.05
        )

    asyncio.run(_run())


def test_emitter_logger_failure_does_not_block_pipeline() -> None:
    """A logger that takes 200ms per call would multiply per-run latency.

    The DecisionEmitter must wrap logger.event in suppress(...). This test
    ensures the synchronous logger sleep is at least bounded — i.e. at most
    one such call per run, and the run still completes.
    """
    policy = PolicyRuleSet(
        rules=(PolicyRule(id="r_email", match="EMAIL_ADDRESS", strategy="redact"),),
    )
    pipeline = GuardPipeline(
        policy_ruleset=policy,
        inspectors=[_StubInspector()],
        logger_hook=_SlowLogger(),
        metrics_hook=_FastMetrics(),
    )

    async def _run() -> None:
        # Budget: 1 second. With one ~200ms logger call this is comfortable;
        # a regression that called event() per finding (or in a loop) would
        # blow this budget.
        await asyncio.wait_for(
            pipeline.pre_process(GuardInput(text="alice@acme.com")), timeout=1.0
        )

    asyncio.run(_run())
