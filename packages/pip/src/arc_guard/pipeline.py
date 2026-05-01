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
from typing import Any

from arc_guard_core.observability import Logger, MetricSink, NullLogger, NullMetricSink
from arc_guard_core.policy import PolicyRuleSet
from arc_guard_core.protocols.flag_provider import FlagProvider
from arc_guard_core.protocols.inspector import Inspector
from arc_guard_core.protocols.middleware import Middleware
from arc_guard_core.protocols.policy_router import PolicyRouter
from arc_guard_core.protocols.reporter import Reporter
from arc_guard_core.protocols.strategy import ActionStrategy
from arc_guard_core.types import GuardInput, GuardResult

from arc_guard.config_env import GuardConfig
from arc_guard.decision.emitter import DecisionEmitter
from arc_guard.flags.env_provider import EnvFlagProvider
from arc_guard.flags.static_provider import StaticFlagProvider
from arc_guard.inspectors.injection import InjectionInspector
from arc_guard.inspectors.presidio import PresidioInspector
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
        # Spec 003 — opt-in policy routing
        policy_ruleset: PolicyRuleSet | None = None,
        policy_router: PolicyRouter | None = None,
        logger_hook: Logger | None = None,
        metrics_hook: MetricSink | None = None,
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

        Spec 002 default chain: ``InjectionInspector`` + ``PresidioInspector``.
        Spec 005 will reintroduce semantic / fidelity inspectors under the
        intent-fidelity contract.
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
        """Build the new GuardResult from a RoutedOutcome (Spec 003 T039)."""
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

        # --- Inspector chain ---
        inspectors = self._explicit_inspectors or self._build_inspector_chain()
        had_error = False

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

        # --- ActionStrategy / PolicyRouter ---
        if self._policy_ruleset is not None:
            # Spec 003 — opt-in policy routing path.
            import time

            router = self._policy_router or RuleBasedPolicyRouter()
            t0 = time.perf_counter()
            outcome = router.route(result, self._policy_ruleset)
            latency_ms = (time.perf_counter() - t0) * 1000.0
            result = self._apply_outcome(result, outcome)
            record = self._decision_emitter.build(result, outcome, latency_ms)
            self._last_decision = record
            self._decision_emitter.emit(
                record,
                logger=self._logger_hook,
                metrics=self._metrics_hook,
            )
        elif result.findings:
            # Spec 001/002 legacy path — single-strategy chain.
            strategy = self._resolve_strategy()
            new_text, decisions = strategy.apply(result.text, result.findings)
            # Strategy `.name` attribute drives the legacy aggregate action.
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

        # --- Reporter (fire-and-forget) ---
        asyncio.ensure_future(self._fire_report(result))

        return result

    async def _fire_report(self, result: GuardResult) -> None:
        try:
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
