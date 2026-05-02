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
import contextvars
import logging
import time
import uuid
from typing import Any, Final

from arc_guard_core.exceptions import ConfigCrossFieldError
from arc_guard_core.failure_modes import lookup_rule
from arc_guard_core.fidelity import NOT_MEASURED, FidelityScore
from arc_guard_core.jailbreak import JailbreakSignal
from arc_guard_core.observability_config import (
    FidelityThresholds,
    JailbreakThresholds,
)
from arc_guard_core.observability import (
    Logger,
    MetricSink,
    NullLogger,
    NullMetricSink,
    NullTracer,
    Tracer,
)
from arc_guard_core.policy import PolicyRuleSet
from arc_guard_core.protocols.fidelity_scorer import FidelityScorer
from arc_guard_core.protocols.flag_provider import FlagProvider
from arc_guard_core.protocols.inspector import Inspector
from arc_guard_core.protocols.intent_encoder import (
    IntentEncoder,
    IntentRepresentation,
)
from arc_guard_core.protocols.jailbreak_detector import JailbreakDetector
from arc_guard_core.protocols.middleware import Middleware
from arc_guard_core.protocols.policy_router import PolicyRouter
from arc_guard_core.protocols.rehydration_verifier import RehydrationVerifier
from arc_guard_core.protocols.reporter import Reporter
from arc_guard_core.protocols.strategy import ActionStrategy
from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.stages import (
    STAGE_CLASSIFY,
    STAGE_DECISION_EMIT,
    STAGE_DEFEND,
    STAGE_EXECUTE,
    STAGE_REFUSAL,
    STAGE_REHYDRATE,
    STAGE_REPORT,
    STAGE_ROUTE,
    STAGE_VERIFY,
)
from arc_guard_core.types import (
    Finding,
    GuardInput,
    GuardResult,
    RefusalEnvelope,
    RiskLevel,
)

from arc_guard.concurrency.offload import run_off_loop
from arc_guard.config_env import GuardConfig
from arc_guard.decision.emitter import DecisionEmitter
from arc_guard.fidelity.ladder import apply_fidelity_ladder
from arc_guard.fidelity.scorer import NullFidelityScorer, score_fidelity
from arc_guard.jailbreak.detector import (
    GUARD_JAILBREAK_DETECTED_EVENT,
    RuleBasedJailbreakDetector,
)
from arc_guard.jailbreak.ladder import apply_jailbreak_ladder
from arc_guard.rehydration.apply import apply_rehydration
from arc_guard.rehydration.verifier import NullRehydrationVerifier
from arc_guard.flags.env_provider import EnvFlagProvider
from arc_guard.flags.static_provider import StaticFlagProvider
from arc_guard.inspectors.injection import InjectionInspector
from arc_guard.inspectors.presidio import PresidioInspector
from arc_guard.intent.capture import NullIntentEncoder, capture_intent
from arc_guard.intent.lock import build_intent_lock
from arc_guard.observability.attributes import BoundedRedactor
from arc_guard.observability.sampling import RunSampler, build_run_sampler
from arc_guard.observability.stage_runner import emit_stage_failed, stage_runner
from arc_guard.policy import validate_strategies_registered
from arc_guard.policy.router import RuleBasedPolicyRouter
from arc_guard.refusal.builder import RefusalBuilder
from arc_guard.reporters.null_reporter import NullReporter
from arc_guard.strategies.block import BlockStrategy
from arc_guard.strategies.hash import HashStrategy
from arc_guard.strategies.redact import RedactStrategy

logger = logging.getLogger("arc_guard")

# Tracks the active run's correlation_id so a recursive ``pre_process``
# call inside a strategy automatically sees the outer run's id as its
# parent. ``ContextVar`` is asyncio-aware and copy-on-fork, so each
# task gets its own value without explicit threading.
_ACTIVE_CORRELATION_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "arc_guard_active_correlation_id", default=None,
)

_STRATEGIES: dict[str, ActionStrategy] = {
    "redact": RedactStrategy(),
    "hash": HashStrategy(),
    "block": BlockStrategy(),
}

# Used when no ``ObservabilityConfig`` is wired through the pipeline's
# config (e.g. the legacy single-strategy path that never got an
# observability block). Equivalent to constructing
# ``FidelityThresholds()`` per call but cheaper.
_DEFAULT_FIDELITY_THRESHOLDS: Final[FidelityThresholds] = FidelityThresholds()
_DEFAULT_JAILBREAK_THRESHOLDS: Final[JailbreakThresholds] = JailbreakThresholds()


_JAILBREAK_CATEGORY_TO_ENTITY_TYPE = {
    "role_play": "JAILBREAK_ROLE_PLAY",
    "hypothetical": "JAILBREAK_HYPOTHETICAL",
    "policy_erosion": "JAILBREAK_POLICY_EROSION",
    "indirect_injection": "JAILBREAK_INDIRECT_INJECTION",
    "direct_override": "JAILBREAK_DIRECT_OVERRIDE",
}


def _signal_to_finding(signal: JailbreakSignal) -> Finding:
    """Convert a ``JailbreakSignal`` to a ``Finding`` for the policy router.

    The detector operates at document granularity rather than tracking
    span positions, so the finding records ``start=0, end=1`` as a
    placeholder span. The score carries the signal's confidence so
    downstream aggregation rules (precedence, risk-band evaluation)
    use it directly.
    """
    entity_type = _JAILBREAK_CATEGORY_TO_ENTITY_TYPE[signal.category]
    return Finding(
        entity_type=entity_type,
        start=0,
        end=1,
        risk_level=RiskLevel.CRITICAL,
        inspector=signal.detector_id,
        score=signal.confidence,
        metadata={
            "jailbreak_category": signal.category,
            "evidence_reference": signal.evidence_reference,
        },
    )


def _entity_map_from_outcome(outcome: Any) -> dict[str, str]:
    """Extract a ``placeholder → original_value`` map from a routed outcome.

    Today the existing ``RuleBasedPolicyRouter`` exposes per-finding
    transforms but does not surface the original entity values on the
    outcome. The map is left empty in this iteration; a subsequent
    spec wires the strategy decisions to expose the map. Returning
    an empty dict keeps the rehydrate stage a no-op until that wiring
    lands.
    """
    if outcome is None:
        return {}
    raw_map: Any = getattr(outcome, "entity_map", None)
    if isinstance(raw_map, dict):
        return {str(k): str(v) for k, v in raw_map.items() if k}
    return {}


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
        # Pluggable Protocol implementations (NOT observability sinks —
        # bare names follow the policy_router / inspectors convention).
        # Default to the null pair so the offline-capable rule holds:
        # without any concrete extra installed, the pipeline runs and the
        # fidelity score is the documented NOT_MEASURED sentinel.
        intent_encoder: IntentEncoder | None = None,
        fidelity_scorer: FidelityScorer | None = None,
        rehydration_verifier: RehydrationVerifier | None = None,
        jailbreak_detector: JailbreakDetector | None = None,
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
        self._intent_encoder: IntentEncoder = intent_encoder or NullIntentEncoder()
        self._fidelity_scorer: FidelityScorer = fidelity_scorer or NullFidelityScorer()
        self._rehydration_verifier: RehydrationVerifier = (
            rehydration_verifier or NullRehydrationVerifier()
        )
        self._jailbreak_detector: JailbreakDetector = (
            jailbreak_detector or RuleBasedJailbreakDetector()
        )
        self._decision_emitter = DecisionEmitter()
        self._last_decision: Any = None  # tests / dev tooling read this
        # Validate at construction so unknown strategies fail eagerly.
        if self._policy_ruleset is not None:
            validate_strategies_registered(self._policy_ruleset)
        # Eager pairing check: a misconfigured encoder/scorer pair would
        # silently produce meaningless scores at runtime, so the
        # construction call fails instead.
        if not self._fidelity_scorer.compatible_with(self._intent_encoder):
            raise ConfigCrossFieldError(
                "intent_encoder is incompatible with fidelity_scorer",
                code="config.cross_field_violation",
                details={
                    "encoder_id": self._intent_encoder.encoder_id,
                    "scorer": type(self._fidelity_scorer).__name__,
                },
            )

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
        sampler: RunSampler | None = None,
    ) -> dict[str, Any]:
        if sampler is not None:
            tracer: Any = sampler.tracer
            logger_hook: Any = sampler.logger
            metric_sink: Any = sampler.metric_sink
        else:
            tracer = self._tracer_hook
            logger_hook = self._logger_hook
            metric_sink = self._metrics_hook
        return {
            "correlation_id": correlation_id,
            "decision_id": decision_id,
            "tracer": tracer,
            "logger": logger_hook,
            "metric_sink": metric_sink,
            "redactor": redactor,
        }

    def _build_closed_failure_envelope(
        self,
        exc: BaseException,
        correlation_id: str,
        decision_id: str,
    ) -> RefusalEnvelope:
        """Build the refusal envelope for a closed-posture stage failure.

        Walks ``FAIL_RULE`` to find the rule for the exception type and
        constructs a refusal envelope from the registered template. Any
        uncategorized exception falls through to the unknown rule, which
        carries ``RefusalCode.INTERNAL_UNKNOWN_ERROR``.
        """
        rule, _posture = lookup_rule(type(exc))
        refusal_code = rule.refusal_code or RefusalCode.INTERNAL_UNKNOWN_ERROR
        return RefusalBuilder().build_internal_failure(
            refusal_code=refusal_code,
            exception_type=type(exc).__name__,
            correlation_id=correlation_id,
            decision_id=decision_id,
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

        correlation_id, decision_id = self._run_ids(guard_input)
        # Recursive-run detection: if the active context already has a
        # correlation_id (set by an enclosing pipeline run on the same
        # asyncio task), record it as the parent so emissions can be
        # linked across the nested runs. The current run sets its own
        # id as the active id, scoped via ContextVar.set / .reset so
        # the parent's id is restored on return.
        parent_correlation_id = _ACTIVE_CORRELATION_ID.get()
        active_token = _ACTIVE_CORRELATION_ID.set(correlation_id)
        # Per-run redactor: scoped to this run's input text so the
        # substring-rejection branch can scan against the actual originals.
        # Constructed fresh per run so concurrent runs do not share the
        # ``_run_originals`` field on the shared pipeline's redactor.
        observability_config = getattr(self._config, "observability", None)
        redactor = BoundedRedactor(observability_config) if observability_config else None
        if redactor is not None:
            redactor.set_run_originals((guard_input.text,))
        # Per-run sampler: buffered tracer + log-level-floor logger.
        # At run end we call ``sampler.finalize(refusal_present=...)``
        # to either flush or drop the buffered emissions.
        sampler: RunSampler | None = None
        if observability_config is not None:
            sampler = build_run_sampler(
                observability_config,
                tracer=self._tracer_hook,
                logger=self._logger_hook,
                metric_sink=self._metrics_hook,
            )
        run_total_started = time.monotonic_ns()
        run_logger = sampler.logger if sampler is not None else self._logger_hook
        run_started_fields: dict[str, Any] = {
            "correlation_id": correlation_id,
            "decision_id": decision_id,
            "input_size_bytes": len(guard_input.text.encode("utf-8")),
        }
        if parent_correlation_id is not None:
            run_started_fields["parent_run_correlation_id"] = parent_correlation_id
        run_logger.event(
            "guard.run.started",
            level="info",
            **run_started_fields,
        )

        # --- Middleware before ---
        effective_input = guard_input
        for mw in self._middlewares:
            try:
                effective_input = await mw.before(effective_input)
            except Exception as exc:
                logger.warning("Middleware.before() raised: %s — using original input", exc)
                effective_input = guard_input

        # --- Intent capture (STAGE_DEFEND) ---
        # Runs before classify/sanitize so the encoder sees the original
        # prompt text, not the masked version. The captured representation
        # flows to the verify stage via a per-run local variable; it is
        # never persisted on shared state so concurrent runs stay isolated.
        captured_intent: IntentRepresentation | None = None
        try:
            with stage_runner(
                STAGE_DEFEND,
                **self._stage_kwargs(correlation_id, decision_id, redactor, sampler),
            ):
                defend_logger = sampler.logger if sampler is not None else self._logger_hook
                captured_intent = await capture_intent(
                    effective_input.text,
                    encoder=self._intent_encoder,
                    correlation_id=correlation_id,
                    decision_id=decision_id,
                    logger=defend_logger,
                    metric_sink=self._metrics_hook,
                )
        except Exception as exc:
            # IntentEncoderError is closed-conservative — degrade to the
            # NOT_MEASURED sentinel and continue. Other exceptions also
            # fall through here because the encoder is non-safety-critical.
            logger.warning("Intent capture raised %s — degrading to sentinel", exc)
            captured_intent = None

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

        jailbreak_signals: tuple[JailbreakSignal, ...] = ()
        with stage_runner(
            STAGE_CLASSIFY, **self._stage_kwargs(correlation_id, decision_id, redactor, sampler)
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
                    # Emit stage.failed for the per-inspector failure even
                    # though the inspector loop swallows it for fail-open
                    # continuation. Without this emission the failure
                    # would be invisible to operators.
                    emit_stage_failed(
                        stage=STAGE_CLASSIFY,
                        exc=exc,
                        correlation_id=correlation_id,
                        decision_id=decision_id,
                        logger=self._logger_hook,
                        metric_sink=self._metrics_hook,
                    )
                    had_error = True
            # --- Jailbreak detector (runs alongside the inspector chain) ---
            # Signals are emitted as Finding entries so the existing
            # policy router's aggregation rules apply unchanged.
            try:
                jailbreak_signals = self._jailbreak_detector.detect(
                    effective_input.text,
                    conversation_state=(
                        effective_input.context.conversation_state
                        if effective_input.context is not None
                        else None
                    ),
                )
                if jailbreak_signals:
                    classify_logger = (
                        sampler.logger if sampler is not None else self._logger_hook
                    )
                    new_findings = list(result.findings)
                    for signal in jailbreak_signals:
                        new_findings.append(_signal_to_finding(signal))
                        classify_logger.event(
                            GUARD_JAILBREAK_DETECTED_EVENT,
                            level="info",
                            correlation_id=correlation_id,
                            decision_id=decision_id,
                            category=signal.category,
                            confidence=signal.confidence,
                            detector_id=signal.detector_id,
                        )
                        self._metrics_hook.counter(
                            "arc_guardrails.jailbreak.detected",
                            attributes={
                                "category": signal.category,
                                "stage": STAGE_CLASSIFY,
                            },
                        )
                    import dataclasses as _dc

                    result = _dc.replace(
                        result, findings=tuple(new_findings),
                    )
            except Exception as exc:
                logger.warning(
                    "Jailbreak detector raised: %s — fail-open, no signal", exc,
                )
                emit_stage_failed(
                    stage=STAGE_CLASSIFY,
                    exc=exc,
                    correlation_id=correlation_id,
                    decision_id=decision_id,
                    logger=self._logger_hook,
                    metric_sink=self._metrics_hook,
                )
                jailbreak_signals = ()

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
        outcome: Any = None
        latency_ms: float = 0.0
        if self._policy_ruleset is not None:
            # Opt-in policy routing: per-finding decisions, aggregated band,
            # decision-record emission.
            router = self._policy_router or RuleBasedPolicyRouter()
            try:
                with stage_runner(
                    STAGE_ROUTE,
                    **self._stage_kwargs(correlation_id, decision_id, redactor, sampler),
                ):
                    t0 = time.perf_counter()
                    outcome = router.route(result, self._policy_ruleset)
                    latency_ms = (time.perf_counter() - t0) * 1000.0
                    result = self._apply_outcome(result, outcome)
                    band_obj = getattr(outcome, "aggregate_band", None)
                    outcome_band = (
                        band_obj.value if hasattr(band_obj, "value") else str(band_obj or "LOW")
                    )
            except Exception as exc:
                # Closed-posture short-circuit: build internal-failure
                # refusal, populate result, skip remaining stages.
                _rule, posture = lookup_rule(type(exc))
                if posture == "closed":
                    refusal = self._build_closed_failure_envelope(
                        exc, correlation_id, decision_id,
                    )
                    result = GuardResult(
                        text="",
                        action="block",
                        findings=result.findings,
                        decisions=(),
                        refusal=refusal,
                        bypass_reason=result.bypass_reason,
                        phase=result.phase,
                    )
                    outcome_band = "CRITICAL"
                    outcome = None  # decision-emit branch skipped
                # ``open`` or ``closed-conservative`` — log already fired
                # in stage_runner; continue the run unchanged.
            # STAGE_REFUSAL marker — fires only when the run produced a refusal
            # envelope. The construction itself happens inside the router; this
            # marker makes the existence observable AND records the refusal's
            # code, trigger, and policy as a structured event so observers can
            # filter on the refusal class without correlating to the
            # decision record.
            if result.refusal is not None:
                with stage_runner(
                    STAGE_REFUSAL,
                    **self._stage_kwargs(correlation_id, decision_id, redactor, sampler),
                ):
                    refusal_logger = (
                        sampler.logger if sampler is not None else self._logger_hook
                    )
                    refusal_logger.event(
                        "guard.refusal.constructed",
                        level="info",
                        correlation_id=correlation_id,
                        decision_id=decision_id,
                        refusal_code=str(result.refusal.code),
                        refusal_trigger=result.refusal.trigger,
                        refusal_policy=result.refusal.policy,
                    )
                    self._metrics_hook.counter(
                        "arc_guardrails.refusal.emitted",
                        attributes={
                            "stage": "refusal",
                            "refusal_code": str(result.refusal.code),
                        },
                    )
            # STAGE_DECISION_EMIT runs AFTER STAGE_VERIFY (below), so the
            # built record carries the fidelity score. ``outcome`` and
            # ``latency_ms`` flow through from this branch's locals to
            # the post-verify decision-emit block.
        elif result.findings:
            # Legacy single-strategy chain: pick one strategy from flags
            # (default ``redact``) and apply it across all findings.
            # ``ActionStrategy.apply`` is sync per Protocol; route it
            # through ``run_off_loop`` so a strategy that does blocking
            # work (regex over a large blob, model inference) does not
            # stall the asyncio event loop. The offload helper bumps
            # the offload counter so operators can dashboard how often
            # the path fires.
            try:
                with stage_runner(
                    STAGE_EXECUTE,
                    **self._stage_kwargs(correlation_id, decision_id, redactor, sampler),
                ):
                    strategy = self._resolve_strategy()
                    new_text, decisions = await run_off_loop(
                        strategy.apply,
                        result.text,
                        result.findings,
                        stage=STAGE_EXECUTE,
                        metric_sink=self._metrics_hook,
                    )
                    action = getattr(strategy, "name", "redact")
                    result = GuardResult(
                        text=new_text,
                        action=action,
                        findings=result.findings,
                        decisions=tuple(decisions),
                        bypass_reason=result.bypass_reason,
                        phase=result.phase,
                    )
            except Exception as exc:
                _rule, posture = lookup_rule(type(exc))
                if posture == "closed":
                    refusal = self._build_closed_failure_envelope(
                        exc, correlation_id, decision_id,
                    )
                    result = GuardResult(
                        text="",
                        action="block",
                        findings=result.findings,
                        decisions=(),
                        refusal=refusal,
                        bypass_reason=result.bypass_reason,
                        phase=result.phase,
                    )
                    outcome_band = "CRITICAL"

        # --- Fidelity score (STAGE_VERIFY) ---
        # Runs after the existing execute / refusal-construction flow
        # but BEFORE STAGE_DECISION_EMIT so the score lands on the
        # DecisionRecord the emitter builds. Skipped on
        # refused-before-generation runs (those that produced a
        # policy refusal) — there is no answer to score.
        fidelity_score: FidelityScore = NOT_MEASURED
        if captured_intent is not None and result.refusal is None:
            try:
                with stage_runner(
                    STAGE_VERIFY,
                    **self._stage_kwargs(
                        correlation_id, decision_id, redactor, sampler,
                    ),
                ):
                    verify_logger = (
                        sampler.logger if sampler is not None else self._logger_hook
                    )
                    thresholds = (
                        observability_config.fidelity_thresholds
                        if observability_config is not None
                        else _DEFAULT_FIDELITY_THRESHOLDS
                    )
                    answer_representation = await run_off_loop(
                        self._intent_encoder.encode,
                        result.text,
                        stage="verify",
                        metric_sink=self._metrics_hook,
                    )
                    fidelity_score = await score_fidelity(
                        captured_intent,
                        answer_representation,
                        scorer=self._fidelity_scorer,
                        thresholds=thresholds,
                        correlation_id=correlation_id,
                        decision_id=decision_id,
                        logger=verify_logger,
                        metric_sink=self._metrics_hook,
                    )
            except Exception as exc:
                logger.warning(
                    "Fidelity scoring raised %s — degrading to sentinel", exc,
                )
                fidelity_score = NOT_MEASURED
        # Attach the score to the result (preserves frozen=True via replace).
        if result.fidelity_score != fidelity_score:
            import dataclasses as _dc

            result = _dc.replace(result, fidelity_score=fidelity_score)

        # Apply the jailbreak threshold-driven action ladder. Runs
        # BEFORE the fidelity ladder so a strong-detector refusal
        # (risk class) takes precedence over fidelity (additive class).
        # Risk-precedence is enforced inside the ladder (no-op when
        # ``result.action == "block"`` or ``result.refusal is not None``).
        jailbreak_thresholds = (
            observability_config.jailbreak_thresholds
            if observability_config is not None
            else _DEFAULT_JAILBREAK_THRESHOLDS
        )
        result = apply_jailbreak_ladder(
            result, jailbreak_signals, jailbreak_thresholds,
        )

        # Apply the fidelity threshold-driven action ladder. Reads
        # ``observability_config.fidelity_thresholds`` (or the default
        # tuple) and dispatches warn / clarify / refuse per band.
        # Risk-precedence is enforced inside the ladder (no-op when
        # ``result.action == "block"`` or ``result.refusal is not None``).
        ladder_thresholds = (
            observability_config.fidelity_thresholds
            if observability_config is not None
            else _DEFAULT_FIDELITY_THRESHOLDS
        )
        result = apply_fidelity_ladder(result, fidelity_score, ladder_thresholds)

        # --- Rehydration safety (STAGE_REHYDRATE) ---
        # Runs only when sanitization actually fired (entity_map is
        # non-empty) and the run completed generation (no risk-band
        # refusal). The verifier checks structural safety; the apply
        # helper substitutes only the placeholders the verifier accepts.
        # Today the entity_map is passed in from policy-router transforms
        # via a per-run state holder; when no transform produced a map,
        # the rehydrate stage is a no-op.
        entity_map = _entity_map_from_outcome(outcome)
        if entity_map and result.refusal is None:
            with stage_runner(
                STAGE_REHYDRATE,
                **self._stage_kwargs(correlation_id, decision_id, redactor, sampler),
            ):
                rehydrate_logger = (
                    sampler.logger if sampler is not None else self._logger_hook
                )
                try:
                    verdict = self._rehydration_verifier.verify(
                        sanitized_prompt=effective_input.text,
                        rehydration_candidate=result.text,
                        entity_map=entity_map,
                    )
                    new_text = apply_rehydration(
                        result.text,
                        verdict,
                        entity_map,
                        correlation_id=correlation_id,
                        decision_id=decision_id,
                        logger=rehydrate_logger,
                        metric_sink=self._metrics_hook,
                    )
                    if new_text != result.text:
                        import dataclasses as _dc

                        result = _dc.replace(result, text=new_text)
                except Exception as exc:
                    logger.warning(
                        "Rehydration verifier raised %s — keeping placeholders", exc,
                    )

        # --- Build the intent lock binding ---
        # The lock contains content-addressed hashes of the original
        # prompt, the sanitized prompt, and (when applicable) the
        # rehydrated answer. Hashes are SHA-256 over canonicalized text;
        # raw payloads never appear in the lock.
        intent_lock = None
        if captured_intent is not None:
            rehydrated_text_for_lock: str | None
            if result.refusal is not None:
                # Refused before generation — there is no answer to hash.
                rehydrated_text_for_lock = None
            else:
                rehydrated_text_for_lock = result.text
            try:
                intent_lock = build_intent_lock(
                    original_text=guard_input.text,
                    sanitized_text=effective_input.text,
                    rehydrated_text=rehydrated_text_for_lock,
                    encoder_id=(
                        self._intent_encoder.encoder_id
                        if not isinstance(self._intent_encoder, NullIntentEncoder)
                        else None
                    ),
                )
            except Exception as exc:
                logger.warning("Intent-lock build raised %s — omitting lock", exc)
                intent_lock = None

        # --- Decision record emission (STAGE_DECISION_EMIT) ---
        # Only emits when the policy router actually ran (``outcome`` is
        # not None). The record carries the fidelity score from the
        # verify stage above and the intent lock from the defend chain.
        if outcome is not None:
            with stage_runner(
                STAGE_DECISION_EMIT,
                **self._stage_kwargs(correlation_id, decision_id, redactor, sampler),
            ):
                record = self._decision_emitter.build(
                    result, outcome, latency_ms,
                    fidelity_score=fidelity_score,
                    intent_lock=intent_lock,
                )
                self._last_decision = record
                self._decision_emitter.emit(
                    record,
                    logger=self._logger_hook,
                    metrics=self._metrics_hook,
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
                sampler=sampler,
            )
        )

        # --- Run-level completion event + total latency histogram ---
        total_ms = (time.monotonic_ns() - run_total_started) / 1_000_000
        risk_band = outcome_band
        run_logger.event(
            "guard.run.completed",
            level="info",
            correlation_id=correlation_id,
            decision_id=decision_id,
            action=result.action,
            risk_band=risk_band,
            total_duration_ms=total_ms,
        )
        # Metrics are never sampled — they go directly to the real sink.
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

        # --- Sampler finalization ---
        # Decide whether to flush or drop the buffered span / event
        # emissions. Refusal-class runs always flush when the
        # ``refusal_always_emits`` knob is on. Failure events were
        # already forwarded immediately by the buffered logger so
        # they survive the discard branch.
        if sampler is not None:
            sampler.finalize(
                refusal_present=result.refusal is not None,
                correlation_id=correlation_id,
            )

        # Restore the parent run's correlation_id (or None) so a
        # subsequent same-task run does not see this run's id as its
        # parent.
        _ACTIVE_CORRELATION_ID.reset(active_token)

        return result

    async def _fire_report(
        self,
        result: GuardResult,
        *,
        correlation_id: str = "",
        decision_id: str = "",
        redactor: BoundedRedactor | None = None,
        sampler: RunSampler | None = None,
    ) -> None:
        try:
            with stage_runner(
                STAGE_REPORT,
                **self._stage_kwargs(correlation_id, decision_id, redactor, sampler),
            ):
                await self._reporter.report(result)
        except Exception as exc:
            # The stage_runner already emitted stage.failed in its
            # catch-block via the shared ``emit_stage_failed`` helper;
            # fail-open per the foundation ``ReporterError.__failure_mode__``.
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
