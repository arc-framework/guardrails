"""GuardPipeline — Chain-of-Responsibility orchestrator for arc-guard.

The pipeline implements the Guard protocol and coordinates:
  1. Middleware.before() hook
  2. Inspector chain (Chain of Responsibility)
  3. ActionStrategy (redact / hash / block)
  4. Middleware.after() hook
  5. Reporter.report() (fire-and-forget)

Fail-open guarantees:
  - Guard disabled → bypass_reason="disabled", text unchanged
  - Inspector raises → bypass_reason="error" logged, passes unchanged to next inspector
  - Middleware raises → logged, uses original input/result (fail-open)
  - Reporter raises → caught internally (never reaches pipeline)
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from arc_guard_core.observability import (
    Logger,
    MetricSink,
    NullLogger,
    NullMetricSink,
    NullTracer,
    Tracer,
)
from arc_guard_core.policy import PolicyRuleSet
from arc_guard_core.protocols.flag_provider import FlagProvider
from arc_guard_core.protocols.inspector import Inspector
from arc_guard_core.protocols.middleware import Middleware
from arc_guard_core.protocols.policy_router import PolicyRouter
from arc_guard_core.protocols.reporter import Reporter
from arc_guard_core.protocols.strategy import ActionStrategy
from arc_guard_core.stages import (
    STAGE_CLASSIFY,
    STAGE_DECISION_EMIT,
    STAGE_EXECUTE,
    STAGE_REFUSAL,
    STAGE_REPORT,
    STAGE_ROUTE,
)
from arc_guard_core.types import GuardInput, GuardResult

from arc_guard.config_env import GuardConfig
from arc_guard.decision.emitter import DecisionEmitter
from arc_guard.flags.env_provider import EnvFlagProvider
from arc_guard.flags.static_provider import StaticFlagProvider
from arc_guard.inspectors.injection import InjectionInspector
from arc_guard.inspectors.presidio import PresidioInspector
from arc_guard.observability.attributes import BoundedRedactor
from arc_guard.observability.stage_runner import stage_runner
from arc_guard.policy import validate_strategies_registered
from arc_guard.policy.router import RuleBasedPolicyRouter
from arc_guard.reporters.null_reporter import NullReporter
from arc_guard.strategies.block import BlockStrategy
from arc_guard.strategies.hash import HashStrategy
from arc_guard.strategies.redact import RedactStrategy

logger = logging.getLogger("arc_guard")

_STRATEGIES: dict[str, ActionStrategy] = {
    "redact": RedactStrategy(),
    "hash": HashStrategy(),
    "block": BlockStrategy(),
}


class GuardPipeline:
    """Chain-of-Responsibility pipeline implementing the Guard protocol.

    Args:
        config: Structural settings (entities, language, model paths).
        flags: Runtime behavioral knobs. Defaults to EnvFlagProvider().
        inspectors: Explicit inspector chain. When None, the default chain is
            built from flags at each call (respects lite_mode).
        middlewares: Optional list of middleware hooks.
        reporter: Audit sink. Defaults to NullReporter.
        strategies: Strategy map override (for testing).
    """

    def __init__(
        self,
        config: GuardConfig | None = None,
        flags: FlagProvider | None = None,
        inspectors: list[Inspector] | None = None,
        middlewares: list[Middleware] | None = None,
        reporter: Reporter | None = None,
        strategies: dict[str, ActionStrategy] | None = None,
        *,
        # Opt-in policy routing. When `policy_ruleset` is None, the pipeline
        # falls back to the single-strategy chain selected by `flags`.
        policy_ruleset: PolicyRuleSet | None = None,
        policy_router: PolicyRouter | None = None,
        logger_hook: Logger | None = None,
        metrics_hook: MetricSink | None = None,
        tracer_hook: Tracer | None = None,
    ) -> None:
        self._config = config or GuardConfig()
        self._flags = flags or EnvFlagProvider()
        self._explicit_inspectors = inspectors
        self._middlewares = middlewares or []
        self._reporter: Reporter = reporter or NullReporter()
        self._strategies = strategies or _STRATEGIES
        self._policy_ruleset = policy_ruleset
        self._policy_router: PolicyRouter | None = policy_router
        self._logger_hook: Logger = logger_hook or NullLogger()
        self._metrics_hook: MetricSink = metrics_hook or NullMetricSink()
        self._tracer_hook: Tracer = tracer_hook or NullTracer()
        self._decision_emitter = DecisionEmitter()
        self._last_decision: Any = None  # tests / dev tooling read this
        # Validate at construction so unknown strategies fail eagerly.
        if self._policy_ruleset is not None:
            validate_strategies_registered(self._policy_ruleset)

    @classmethod
    def default(
        cls,
        flags: FlagProvider | None = None,
        reporter: Reporter | None = None,
    ) -> GuardPipeline:
        """Build a pipeline with default config and inspector chain.

        The default chain is ``InjectionInspector`` + ``PresidioInspector``.
        A future intent-fidelity contract will reintroduce semantic and
        fidelity inspectors.
        """
        return cls(
            config=GuardConfig.from_env(),
            flags=flags or EnvFlagProvider(),
            reporter=reporter or NullReporter(),
        )

    def _build_inspector_chain(self) -> list[Inspector]:
        """Construct the default inspector chain based on current flags."""
        chain: list[Inspector] = []

        if self._flags.is_enabled("injection_enabled", default=True):
            chain.append(InjectionInspector())

        try:
            chain.append(PresidioInspector(self._config))
        except Exception as exc:
            logger.warning("PresidioInspector unavailable: %s — skipping", exc)

        return chain

    def _resolve_strategy(self) -> ActionStrategy:
        name = self._flags.get_string("action_strategy", default="redact")
        return self._strategies.get(name, self._strategies["redact"])

    def _apply_outcome(self, result: GuardResult, outcome: Any) -> GuardResult:
        """Build the new GuardResult from a RoutedOutcome."""
        return GuardResult(
            text=outcome.transformed_text,
            action=outcome.aggregate_action,
            findings=result.findings,
            decisions=outcome.decisions,
            refusal=outcome.refusal,
            clarification=outcome.clarification,
            bypass_reason=result.bypass_reason,
            phase=result.phase,
        )

    def _run_ids(self, guard_input: GuardInput) -> tuple[str, str]:
        """Resolve correlation_id (from context, or fresh) and a fresh decision_id."""
        ctx_corr: str | None = None
        if guard_input.context is not None:
            ctx_corr = getattr(guard_input.context, "correlation_id", None)
        correlation_id = ctx_corr or uuid.uuid4().hex
        decision_id = uuid.uuid4().hex
        return correlation_id, decision_id

    def _stage_kwargs(
        self,
        correlation_id: str,
        decision_id: str,
        redactor: BoundedRedactor | None = None,
    ) -> dict[str, Any]:
        return {
            "correlation_id": correlation_id,
            "decision_id": decision_id,
            "tracer": self._tracer_hook,
            "logger": self._logger_hook,
            "metric_sink": self._metrics_hook,
            "redactor": redactor,
        }

    async def _run_pipeline(
        self, guard_input: GuardInput, phase: str
    ) -> GuardResult:
        """Core pipeline execution — shared by pre_process and post_process."""

        # --- Guard disabled fast-path ---
        if not self._flags.is_enabled("enabled", default=True):
            return GuardResult(
                text=guard_input.text,
                action="pass",
                findings=(),
                bypass_reason="disabled",
                phase=phase,
            )

        correlation_id, decision_id = self._run_ids(guard_input)
        # Per-run redactor: scoped to this run's input text so the
        # substring-rejection branch can scan against the actual originals.
        # Constructed fresh per run so concurrent runs do not share the
        # ``_run_originals`` field on the shared pipeline's redactor.
        observability_config = getattr(self._config, "observability", None)
        redactor = BoundedRedactor(observability_config) if observability_config else None
        if redactor is not None:
            redactor.set_run_originals((guard_input.text,))
        run_total_started = time.monotonic_ns()
        self._logger_hook.event(
            "guard.run.started",
            level="info",
            correlation_id=correlation_id,
            decision_id=decision_id,
            input_size_bytes=len(guard_input.text.encode("utf-8")),
        )

        # --- Middleware before ---
        effective_input = guard_input
        for mw in self._middlewares:
            try:
                effective_input = await mw.before(effective_input)
            except Exception as exc:
                logger.warning("Middleware.before() raised: %s — using original input", exc)
                effective_input = guard_input

        # --- Build result accumulator ---
        result = GuardResult(
            text=effective_input.text,
            action="pass",
            findings=(),
            bypass_reason=None,
            phase=phase,
        )

        # --- Inspector chain (STAGE_CLASSIFY) ---
        inspectors = self._explicit_inspectors or self._build_inspector_chain()
        had_error = False

        with stage_runner(
            STAGE_CLASSIFY, **self._stage_kwargs(correlation_id, decision_id, redactor)
        ):
            for inspector in inspectors:
                try:
                    result = await inspector.inspect(result)
                except Exception as exc:
                    logger.warning(
                        "Inspector %s raised: %s — fail-open, continuing",
                        type(inspector).__name__,
                        exc,
                    )
                    had_error = True

        if had_error and result.bypass_reason is None:
            result = GuardResult(
                text=result.text,
                action=result.action,
                findings=result.findings,
                bypass_reason="error",
                phase=result.phase,
            )

        # --- ActionStrategy / PolicyRouter (STAGE_ROUTE + STAGE_EXECUTE + STAGE_DECISION_EMIT) ---
        outcome_band: str = "LOW"
        if self._policy_ruleset is not None:
            # Opt-in policy routing: per-finding decisions, aggregated band,
            # decision-record emission.
            router = self._policy_router or RuleBasedPolicyRouter()
            with stage_runner(
                STAGE_ROUTE, **self._stage_kwargs(correlation_id, decision_id, redactor)
            ):
                t0 = time.perf_counter()
                outcome = router.route(result, self._policy_ruleset)
                latency_ms = (time.perf_counter() - t0) * 1000.0
                result = self._apply_outcome(result, outcome)
                band_obj = getattr(outcome, "aggregate_band", None)
                outcome_band = (
                    band_obj.value if hasattr(band_obj, "value") else str(band_obj or "LOW")
                )
            # STAGE_REFUSAL marker — fires only when the run produced a refusal
            # envelope. The construction itself happens inside the router; this
            # marker makes the existence observable without re-doing work.
            if result.refusal is not None:
                with stage_runner(
                    STAGE_REFUSAL, **self._stage_kwargs(correlation_id, decision_id, redactor)
                ):
                    pass
            with stage_runner(
                STAGE_DECISION_EMIT, **self._stage_kwargs(correlation_id, decision_id, redactor)
            ):
                record = self._decision_emitter.build(result, outcome, latency_ms)
                self._last_decision = record
                self._decision_emitter.emit(
                    record,
                    logger=self._logger_hook,
                    metrics=self._metrics_hook,
                )
        elif result.findings:
            # Legacy single-strategy chain: pick one strategy from flags
            # (default ``redact``) and apply it across all findings.
            with stage_runner(
                STAGE_EXECUTE, **self._stage_kwargs(correlation_id, decision_id, redactor)
            ):
                strategy = self._resolve_strategy()
                new_text, decisions = strategy.apply(result.text, result.findings)
                action = getattr(strategy, "name", "redact")
                result = GuardResult(
                    text=new_text,
                    action=action,
                    findings=result.findings,
                    decisions=tuple(decisions),
                    bypass_reason=result.bypass_reason,
                    phase=result.phase,
                )

        # --- Middleware after ---
        for mw in self._middlewares:
            try:
                result = await mw.after(result)
            except Exception as exc:
                logger.warning("Middleware.after() raised: %s — using pre-after result", exc)

        # --- Reporter (fire-and-forget, STAGE_REPORT) ---
        asyncio.ensure_future(
            self._fire_report(
                result,
                correlation_id=correlation_id,
                decision_id=decision_id,
                redactor=redactor,
            )
        )

        # --- Run-level completion event + total latency histogram ---
        total_ms = (time.monotonic_ns() - run_total_started) / 1_000_000
        risk_band = outcome_band
        self._logger_hook.event(
            "guard.run.completed",
            level="info",
            correlation_id=correlation_id,
            decision_id=decision_id,
            action=result.action,
            risk_band=risk_band,
            total_duration_ms=total_ms,
        )
        self._metrics_hook.histogram(
            "arc_guardrails.run.duration",
            total_ms,
            attributes={"correlation_id": correlation_id, "stage": "run"},
        )
        self._metrics_hook.counter(
            "arc_guardrails.run.action",
            1,
            attributes={
                "correlation_id": correlation_id,
                "stage": "run",
                "action": result.action,
                "risk_band": risk_band,
            },
        )

        return result

    async def _fire_report(
        self,
        result: GuardResult,
        *,
        correlation_id: str = "",
        decision_id: str = "",
        redactor: BoundedRedactor | None = None,
    ) -> None:
        try:
            with stage_runner(
                STAGE_REPORT, **self._stage_kwargs(correlation_id, decision_id, redactor)
            ):
                await self._reporter.report(result)
        except Exception as exc:
            logger.warning("Reporter.report() raised: %s", exc)

    async def pre_process(self, guard_input: GuardInput) -> GuardResult:
        """Inspect and transform a user prompt before LLM inference."""
        return await self._run_pipeline(guard_input, "pre_process")

    async def post_process(self, guard_input: GuardInput) -> GuardResult:
        """Inspect and transform the model response after inference."""
        return await self._run_pipeline(guard_input, "post_process")

    @staticmethod
    def from_static_flags(flags_dict: dict[str, Any], **kwargs: Any) -> GuardPipeline:
        """Convenience factory for testing with a fixed flag set."""
        return GuardPipeline(flags=StaticFlagProvider(flags_dict), **kwargs)
