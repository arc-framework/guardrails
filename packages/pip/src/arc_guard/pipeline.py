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
import contextlib
import contextvars
import logging
import time
import uuid
from typing import Any, Final

from arc_guard_core.deception import (
    NOT_MEASURED as DECEPTION_NOT_MEASURED,
)
from arc_guard_core.deception import (
    ConversationState,
    DeceptionScore,
)
from arc_guard_core.exceptions import ConfigCrossFieldError
from arc_guard_core.failure_modes import lookup_rule
from arc_guard_core.fidelity import NOT_MEASURED, FidelityScore
from arc_guard_core.jailbreak import JailbreakSignal
from arc_guard_core.lifecycle import (
    DeceptionScored,
    FidelityScored,
    InspectorFailed,
    InspectorMatchExplain,
    InspectorRan,
    IntentCaptured,
    JailbreakDetected,
    LifecycleEvent,
    LifecycleSink,
    NullLifecycleSink,
    PlaceholderMapBuilt,
    PolicyResolved,
    PolicyRuleEvaluated,
    RefusalProduced,
    RehydrationVerified,
    ReportFlushed,
    SanitizationApplied,
    StageRan,
    StrategyExecuted,
)
from arc_guard_core.lifecycle import (
    DecisionEmitted as LifecycleDecisionEmitted,
)
from arc_guard_core.lifecycle import (
    FindingProduced as LifecycleFindingProduced,
)
from arc_guard_core.observability import (
    Logger,
    MetricSink,
    NullLogger,
    NullMetricSink,
    NullTracer,
    Tracer,
)
from arc_guard_core.observability_config import (
    DeceptionThresholds,
    FidelityThresholds,
    JailbreakThresholds,
)
from arc_guard_core.policy import PolicyRuleSet
from arc_guard_core.protocols.conversation_turn_inspector import (
    ConversationTurnInspector,
)
from arc_guard_core.protocols.explainable_inspector import (
    ExplainableInspector,
)
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
    STAGE_DECEPTION_INSPECT,
    STAGE_DECISION_EMIT,
    STAGE_DEFEND,
    STAGE_EXECUTE,
    STAGE_REFUSAL,
    STAGE_REHYDRATE,
    STAGE_REPORT,
    STAGE_ROUTE,
    STAGE_SANITIZE,
    STAGE_VALIDATE,
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
from arc_guard.deception.inspector import (
    GUARD_DECEPTION_SCORED_EVENT,
    StatefulConversationInspector,
)
from arc_guard.deception.ladder import apply_deception_ladder
from arc_guard.decision.emitter import DecisionEmitter
from arc_guard.fidelity.ladder import apply_fidelity_ladder
from arc_guard.fidelity.scorer import NullFidelityScorer, score_fidelity
from arc_guard.flags.env_provider import EnvFlagProvider
from arc_guard.flags.static_provider import StaticFlagProvider
from arc_guard.inspectors.injection import InjectionInspector
from arc_guard.inspectors.presidio import PresidioInspector
from arc_guard.intent.capture import NullIntentEncoder, capture_intent
from arc_guard.intent.lock import build_intent_lock
from arc_guard.jailbreak.detector import (
    GUARD_JAILBREAK_DETECTED_EVENT,
    RuleBasedJailbreakDetector,
)
from arc_guard.jailbreak.ladder import apply_jailbreak_ladder
from arc_guard.observability.attributes import BoundedRedactor
from arc_guard.observability.sampling import RunSampler, build_run_sampler
from arc_guard.observability.stage_runner import emit_stage_failed, stage_runner
from arc_guard.policy import validate_strategies_registered
from arc_guard.policy.router import RuleBasedPolicyRouter
from arc_guard.refusal.builder import RefusalBuilder
from arc_guard.rehydration.apply import apply_rehydration
from arc_guard.rehydration.verifier import NullRehydrationVerifier
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
_DEFAULT_DECEPTION_THRESHOLDS: Final[DeceptionThresholds] = DeceptionThresholds()


def _band_for_deception_score(
    score: DeceptionScore, thresholds: DeceptionThresholds,
) -> str:
    """Classify a ``DeceptionScore`` into the documented band string.

    INVERSE direction: higher = more risk; ordering is
    ``refuse > clarify > warn``.
    """
    if score.sentinel != "measured" or score.value is None:
        return "not_measured"
    if score.value >= thresholds.refuse:
        return "refuse"
    if score.value >= thresholds.clarify:
        return "clarify"
    if score.value >= thresholds.warn:
        return "warn"
    return "above_warn"


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
        conversation_turn_inspector: ConversationTurnInspector | None = None,
        # Per-request lifecycle observability (additive; default NullLifecycleSink
        # keeps existing GuardPipeline(...) callers behaviorally unchanged).
        lifecycle_hook: LifecycleSink | None = None,
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
        self._conversation_turn_inspector: ConversationTurnInspector = (
            conversation_turn_inspector or StatefulConversationInspector()
        )
        self._lifecycle_hook: LifecycleSink = lifecycle_hook or NullLifecycleSink()
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

    async def _emit_lifecycle(self, event: LifecycleEvent) -> None:
        """Fan an event out to the configured LifecycleSink, fail-open.

        The LifecycleSink contract says implementations MUST NOT raise. We
        belt-and-suspenders that with a try/except so a misbehaving sink can
        never propagate back into the pipeline.
        """
        try:
            await self._lifecycle_hook.emit(event)
        except Exception as exc:  # pragma: no cover — sink failure path
            logger.warning("LifecycleSink.emit() raised: %s", exc)
            with contextlib.suppress(Exception):
                self._metrics_hook.counter("arc_guard.lifecycle.emit.failures")

    @staticmethod
    def _lifecycle_ctx(guard_input: GuardInput) -> tuple[Any | None, str | None]:
        """Extract the (emitter, parent_id) tuple from the input's
        GuardContext.metadata. Returns (None, None) when no emitter is wired
        (SDK-only callers without the api transport).
        """
        if guard_input.context is None or not guard_input.context.metadata:
            return (None, None)
        meta = guard_input.context.metadata
        return meta.get("_lifecycle_emitter"), meta.get("_lifecycle_parent_id")

    async def _emit_via_ctx(
        self,
        guard_input: GuardInput,
        event_class: Any,
        *,
        parent_id_override: str | None = None,
        **fields: Any,
    ) -> Any | None:
        """Emit a typed lifecycle event using the per-rid emitter that the
        api transport stashed in `GuardContext.metadata`. Returns the
        constructed event so callers can capture its `id` for cross-refs.
        Returns None and silently no-ops when no emitter is wired.
        """
        emitter, default_parent = self._lifecycle_ctx(guard_input)
        if emitter is None:
            return None
        try:
            return await emitter.emit(
                event_class,
                parent_id=parent_id_override
                if parent_id_override is not None
                else default_parent,
                **fields,
            )
        except Exception as exc:  # pragma: no cover — sink failure path
            logger.warning("LifecycleEmitter.emit() raised: %s", exc)
            with contextlib.suppress(Exception):
                self._metrics_hook.counter("arc_guard.lifecycle.emit.failures")
            return None

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
        """Build the new GuardResult from a RoutedOutcome.

        Preserves the additive fields (``fidelity_score``,
        ``fidelity_warning``, ``deception_score``, ``conversation_state``)
        from the prior result so downstream stages that re-bind via
        this helper don't lose state.
        """
        return GuardResult(
            text=outcome.transformed_text,
            action=outcome.aggregate_action,
            findings=result.findings,
            decisions=outcome.decisions,
            refusal=outcome.refusal,
            clarification=outcome.clarification,
            bypass_reason=result.bypass_reason,
            phase=result.phase,
            fidelity_score=result.fidelity_score,
            fidelity_warning=result.fidelity_warning,
            deception_score=result.deception_score,
            conversation_state=result.conversation_state,
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

        # --- Input validation marker (STAGE_VALIDATE) ---
        # The pipeline never accepts a malformed ``GuardInput`` — the
        # dataclass + validators at the API boundary reject it before we
        # ever get here. By the time _run_pipeline runs, we know the input
        # is structurally valid, so we record a zero-duration marker so
        # the canvas can show the stage as "completed" rather than dark.
        _t0_validate = time.perf_counter()
        with stage_runner(
            STAGE_VALIDATE,
            **self._stage_kwargs(correlation_id, decision_id, redactor, sampler),
        ):
            pass
        await self._emit_via_ctx(
            guard_input, StageRan, stage=STAGE_VALIDATE,
            duration_ms=(time.perf_counter() - _t0_validate) * 1000,
            status="ok",
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
        _t0_defend = time.perf_counter()
        _defend_status = "ok"
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
            _defend_status = "err"
        _stage_defend_ev = await self._emit_via_ctx(
            guard_input, StageRan, stage=STAGE_DEFEND,
            duration_ms=(time.perf_counter() - _t0_defend) * 1000,
            status=_defend_status,
        )
        if _stage_defend_ev is not None:
            await self._emit_via_ctx(
                guard_input, IntentCaptured,
                parent_id_override=_stage_defend_ev.id,
                encoder_id=self._intent_encoder.encoder_id,
                intent_size_bytes=len(effective_input.text or ""),
            )

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
        _t0_classify = time.perf_counter()
        # Per-finding event ids — captured here so SanitizationApplied /
        # StrategyExecuted in later stages can populate `finding_id` cross-refs.
        _finding_event_ids: dict[int, str] = {}
        with stage_runner(
            STAGE_CLASSIFY, **self._stage_kwargs(correlation_id, decision_id, redactor, sampler)
        ):
            for inspector in inspectors:
                _t0_inspector = time.perf_counter()
                _findings_before = len(result.findings)
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
                    # Conditional InspectorFailed lifecycle event — fires
                    # only on uncaught inspector exception; pipeline still
                    # fail-opens. Traceback id is the exception's repr hash
                    # so operators can correlate to a stack-traced log line
                    # without the lifecycle event carrying full traceback.
                    await self._emit_via_ctx(
                        guard_input, InspectorFailed,
                        inspector_name=type(inspector).__name__,
                        exception_class=type(exc).__name__,
                        traceback_id=f"tb_{abs(hash(repr(exc))) & 0xFFFFFFFF:08x}",
                    )
                # Per-inspector lifecycle event with timing + count.
                _findings_after = len(result.findings)
                _inspector_event = await self._emit_via_ctx(
                    guard_input, InspectorRan,
                    name=type(inspector).__name__,
                    duration_ms=(time.perf_counter() - _t0_inspector) * 1000,
                    findings_count=_findings_after - _findings_before,
                )
                if _inspector_event is not None:
                    # Emit one FindingProduced per finding produced by THIS
                    # inspector. Walk the new tail of the findings list.
                    _new_findings = result.findings[_findings_before:_findings_after]
                    for f in _new_findings:
                        _fp_ev = await self._emit_via_ctx(
                            guard_input, LifecycleFindingProduced,
                            parent_id_override=_inspector_event.id,
                            entity_type=f.entity_type,
                            span=(f.start, f.end),
                            score=f.score or 0.0,
                            risk_level=int(f.risk_level),
                            inspector=type(inspector).__name__,
                        )
                        if _fp_ev is not None:
                            # Index by (start,end) so later stages can resolve.
                            _finding_event_ids[(f.start, f.end)] = _fp_ev.id
                    if isinstance(inspector, ExplainableInspector) and _new_findings:
                        try:
                            _explanations = inspector.explain_matches(
                                result.text, _new_findings
                            )
                        except Exception:
                            _explanations = []
                        for _ex in _explanations:
                            await self._emit_via_ctx(
                                guard_input, InspectorMatchExplain,
                                parent_id_override=_inspector_event.id,
                                inspector=type(inspector).__name__,
                                pattern_id=_ex.pattern_id,
                                matched_span=(_ex.finding.start, _ex.finding.end),
                                explanation=_ex.explanation,
                            )
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
                        # Lifecycle bridge — same hook point, typed event.
                        # evidence_reference is a stable id derived from the
                        # detector + category (not the matched payload). The
                        # dashboard uses this to link to the jailbreak rule
                        # that fired without exposing the matched text.
                        await self._emit_via_ctx(
                            guard_input, JailbreakDetected,
                            detector_id=signal.detector_id,
                            category=signal.category,
                            confidence=signal.confidence,
                            evidence_reference=(
                                f"{signal.detector_id}/{signal.category}"
                                if signal.category
                                else signal.detector_id
                            ),
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
        await self._emit_via_ctx(
            guard_input, StageRan, stage=STAGE_CLASSIFY,
            duration_ms=(time.perf_counter() - _t0_classify) * 1000,
            status="err" if had_error else "ok",
        )

        if had_error and result.bypass_reason is None:
            result = GuardResult(
                text=result.text,
                action=result.action,
                findings=result.findings,
                bypass_reason="error",
                phase=result.phase,
            )

        # --- Deception inspection (STAGE_DECEPTION_INSPECT) ---
        # Runs after STAGE_CLASSIFY and before STAGE_SANITIZE so
        # deception signals are part of the policy-router input. Reads
        # the prior state from ``effective_input.context.conversation_state``
        # (None for single-turn mode); calls the inspector; attaches
        # both the score AND the updated state to result via
        # ``dataclasses.replace`` (top-level fields on GuardResult, NOT
        # under result.context).
        prior_state: ConversationState | None = (
            effective_input.context.conversation_state
            if effective_input.context is not None
            else None
        )
        deception_score: DeceptionScore = DECEPTION_NOT_MEASURED
        updated_state: ConversationState | None = None
        _t0_decept = time.perf_counter()
        _decept_status = "ok"
        _decept_band = "not_measured"
        try:
            with stage_runner(
                STAGE_DECEPTION_INSPECT,
                **self._stage_kwargs(correlation_id, decision_id, redactor, sampler),
            ):
                deception_score, updated_state = (
                    self._conversation_turn_inspector.inspect_turn(
                        effective_input.text, prior_state=prior_state,
                    )
                )
                deception_logger = (
                    sampler.logger if sampler is not None else self._logger_hook
                )
                deception_band = _band_for_deception_score(
                    deception_score,
                    observability_config.deception_thresholds
                    if observability_config is not None
                    else _DEFAULT_DECEPTION_THRESHOLDS,
                )
                _decept_band = deception_band
                deception_logger.event(
                    GUARD_DECEPTION_SCORED_EVENT,
                    level="info",
                    correlation_id=correlation_id,
                    decision_id=decision_id,
                    score_value=deception_score.value,
                    score_sentinel=deception_score.sentinel,
                    band=deception_band,
                    turn_count=updated_state.turn_count,
                )
                self._metrics_hook.counter(
                    "arc_guardrails.deception.score",
                    attributes={
                        "band": deception_band,
                        "sentinel": deception_score.sentinel,
                    },
                )
        except Exception as exc:
            logger.warning(
                "Deception inspector raised %s — degrading to sentinel", exc,
            )
            deception_score = DECEPTION_NOT_MEASURED
            updated_state = None
            _decept_status = "err"
        _stage_decept_ev = await self._emit_via_ctx(
            guard_input, StageRan, stage=STAGE_DECEPTION_INSPECT,
            duration_ms=(time.perf_counter() - _t0_decept) * 1000,
            status=_decept_status,
        )
        if _stage_decept_ev is not None:
            await self._emit_via_ctx(
                guard_input, DeceptionScored,
                parent_id_override=_stage_decept_ev.id,
                score_value=deception_score.value,
                score_sentinel=deception_score.sentinel,
                band=_decept_band,  # type: ignore[arg-type]
                turn_count=updated_state.turn_count if updated_state else 1,
            )

        # Attach both score and updated state to result so the
        # operator's integration can thread the state forward.
        import dataclasses as _dc_dec

        result = _dc_dec.replace(
            result,
            deception_score=deception_score,
            conversation_state=updated_state,
        )

        # --- Sanitization marker (STAGE_SANITIZE) ---
        # The actual placeholder substitution happens inside the strategy
        # invoked by STAGE_EXECUTE below; sanitize is the canonical pipeline
        # boundary at which "we know there are entities and they MAY be
        # placeholdered downstream". Status is "skipped" when there are no
        # findings (nothing to sanitize) so the canvas can render the
        # distinction.
        _t0_sanitize = time.perf_counter()
        with stage_runner(
            STAGE_SANITIZE,
            **self._stage_kwargs(correlation_id, decision_id, redactor, sampler),
        ):
            pass
        await self._emit_via_ctx(
            guard_input, StageRan, stage=STAGE_SANITIZE,
            duration_ms=(time.perf_counter() - _t0_sanitize) * 1000,
            status="ok" if result.findings else "skipped",
        )

        # --- ActionStrategy / PolicyRouter (STAGE_ROUTE + STAGE_EXECUTE + STAGE_DECISION_EMIT) ---
        outcome_band: str = "LOW"
        outcome: Any = None
        latency_ms: float = 0.0
        # When no policy ruleset is wired the canonical route stage is a no-op —
        # the pipeline still considers the routing question, just immediately
        # falls through. Emit a skipped marker so the canvas reflects the
        # decision boundary even on the legacy / pass-through paths.
        if self._policy_ruleset is None:
            await self._emit_via_ctx(
                guard_input, StageRan, stage=STAGE_ROUTE,
                duration_ms=0.0,
                status="skipped",
            )
        if self._policy_ruleset is not None:
            # Opt-in policy routing: per-finding decisions, aggregated band,
            # decision-record emission.
            router = self._policy_router or RuleBasedPolicyRouter()
            _t0_route = time.perf_counter()
            _route_status = "ok"
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
                        fidelity_score=result.fidelity_score,
                        fidelity_warning=result.fidelity_warning,
                        deception_score=result.deception_score,
                        conversation_state=result.conversation_state,
                    )
                    outcome_band = "CRITICAL"
                    outcome = None  # decision-emit branch skipped
                    _route_status = "err"
                # ``open`` or ``closed-conservative`` — log already fired
                # in stage_runner; continue the run unchanged.
            await self._emit_via_ctx(
                guard_input, StageRan, stage=STAGE_ROUTE,
                duration_ms=(time.perf_counter() - _t0_route) * 1000,
                status=_route_status,
            )
            await self._emit_via_ctx(
                guard_input, PolicyResolved,
                max_risk=outcome_band if outcome_band in ("LOW", "MEDIUM", "HIGH", "CRITICAL") else "LOW",
                resolved_action=str(result.action),
                router=type(router).__name__,
            )
            if outcome is not None:
                _fired_ids = set(getattr(outcome, "fired_rule_ids", ()) or ())
                _action_is_user_visible = str(result.action) != "pass"
                _entity_types_in_findings = {f.entity_type for f in result.findings}
                for _rule in self._policy_ruleset.rules:
                    if _rule.id in _fired_ids:
                        _r_outcome = "matched"
                    elif _rule.match in _entity_types_in_findings:
                        _r_outcome = "not_matched"
                    else:
                        _r_outcome = "not_applicable"
                    await self._emit_via_ctx(
                        guard_input, PolicyRuleEvaluated,
                        rule_id=_rule.id,
                        outcome=_r_outcome,
                        contributed_to_action=(_r_outcome == "matched" and _action_is_user_visible),
                    )
            # STAGE_EXECUTE marker — on the policy-ruleset path the strategy
            # work happens inside ``apply_outcome`` (called within route's
            # stage_runner). Emit a marker so the canvas shows execute as
            # having run; status reflects whether route's strategy actually
            # produced a non-None outcome.
            await self._emit_via_ctx(
                guard_input, StageRan, stage=STAGE_EXECUTE,
                duration_ms=0.0,
                status="ok" if outcome is not None else "err",
            )
            # STAGE_REFUSAL marker — fires only when the run produced a refusal
            # envelope. The construction itself happens inside the router; this
            # marker makes the existence observable AND records the refusal's
            # code, trigger, and policy as a structured event so observers can
            # filter on the refusal class without correlating to the
            # decision record.
            if result.refusal is not None:
                _t0_refusal = time.perf_counter()
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
                _stage_ref_ev = await self._emit_via_ctx(
                    guard_input, StageRan, stage=STAGE_REFUSAL,
                    duration_ms=(time.perf_counter() - _t0_refusal) * 1000,
                    status="ok",
                )
                if _stage_ref_ev is not None:
                    await self._emit_via_ctx(
                        guard_input, RefusalProduced,
                        parent_id_override=_stage_ref_ev.id,
                        refusal_code=str(result.refusal.code),
                        human_message_chars=len(result.refusal.human_message or ""),
                        decision_id=decision_id,
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
            _t0_execute = time.perf_counter()
            _execute_status = "ok"
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
                        fidelity_score=result.fidelity_score,
                        fidelity_warning=result.fidelity_warning,
                        deception_score=result.deception_score,
                        conversation_state=result.conversation_state,
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
                        fidelity_score=result.fidelity_score,
                        fidelity_warning=result.fidelity_warning,
                        deception_score=result.deception_score,
                        conversation_state=result.conversation_state,
                    )
                    outcome_band = "CRITICAL"
                    _execute_status = "err"
            _stage_exec_ev = await self._emit_via_ctx(
                guard_input, StageRan, stage=STAGE_EXECUTE,
                duration_ms=(time.perf_counter() - _t0_execute) * 1000,
                status=_execute_status,
            )
            # StrategyExecuted + per-decision SanitizationApplied emissions.
            if _stage_exec_ev is not None and result.decisions:
                _strategy_name = (
                    type(self._resolve_strategy()).__name__ if result.findings else "PassThrough"
                )
                # Pick the first finding as the cross-ref anchor for the
                # strategy as a whole (each decision then carries its own
                # finding_id via SanitizationApplied below).
                _first_finding_id = next(iter(_finding_event_ids.values()), "")
                await self._emit_via_ctx(
                    guard_input, StrategyExecuted,
                    parent_id_override=_stage_exec_ev.id,
                    strategy=_strategy_name,
                    finding_id=_first_finding_id,
                    text_after_size=len(result.text or ""),
                )
                # SanitizationApplied per-finding (only when the action
                # actually mutates text — redact / hash / tokenize).
                # `text_after` is populated only when the configured policy
                # opts into sanitized capture (default: off).
                if str(result.action) in ("redact", "hash", "tokenize"):
                    _emitter, _ = self._lifecycle_ctx(guard_input)
                    _capture_text = (
                        _emitter is not None
                        and _emitter.policy.should_capture_sanitized()
                    )
                    _capture_raw = (
                        _emitter is not None
                        and _emitter.policy.should_capture_raw_input()
                    )
                    _placeholder_map: dict[str, str] = {}
                    for f in result.findings:
                        placeholder = f"[{f.entity_type}]"
                        await self._emit_via_ctx(
                            guard_input, SanitizationApplied,
                            parent_id_override=_stage_exec_ev.id,
                            entity_type=f.entity_type,
                            placeholder=placeholder,
                            span=(f.start, f.end),
                            finding_id=_finding_event_ids.get((f.start, f.end), ""),
                            text_after=result.text if _capture_text else None,
                        )
                        if _capture_raw:
                            # Pre-sanitization slice that produced the
                            # placeholder. Only included when raw-input
                            # capture is opted in (security-sensitive).
                            _placeholder_map[placeholder] = (
                                effective_input.text[f.start:f.end]
                            )
                    # PlaceholderMapBuilt — per-request summary, conditional
                    # event. Carries entity_types + count always; the raw
                    # placeholder→original map only when raw capture is on.
                    await self._emit_via_ctx(
                        guard_input, PlaceholderMapBuilt,
                        parent_id_override=_stage_exec_ev.id,
                        placeholder_count=len(result.findings),
                        entity_types=sorted({f.entity_type for f in result.findings}),
                        map=_placeholder_map if _capture_raw else None,
                    )
        else:
            # Pass-through: no policy ruleset and no findings. Emit a
            # ``skipped`` execute marker so the canvas can show the stage
            # as having been considered (and intentionally bypassed).
            await self._emit_via_ctx(
                guard_input, StageRan, stage=STAGE_EXECUTE,
                duration_ms=0.0,
                status="skipped",
            )

        # --- Fidelity score (STAGE_VERIFY) ---
        # Runs after the existing execute / refusal-construction flow
        # but BEFORE STAGE_DECISION_EMIT so the score lands on the
        # DecisionRecord the emitter builds. Skipped on
        # refused-before-generation runs (those that produced a
        # policy refusal) — there is no answer to score.
        fidelity_score: FidelityScore = NOT_MEASURED
        _t0_verify = time.perf_counter()
        _verify_status = "ok"
        _verify_ran = False
        if captured_intent is not None and result.refusal is None:
            _verify_ran = True
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
                _verify_status = "err"
        if _verify_ran:
            _stage_verify_ev = await self._emit_via_ctx(
                guard_input, StageRan, stage=STAGE_VERIFY,
                duration_ms=(time.perf_counter() - _t0_verify) * 1000,
                status=_verify_status,
            )
            if _stage_verify_ev is not None:
                await self._emit_via_ctx(
                    guard_input, FidelityScored,
                    parent_id_override=_stage_verify_ev.id,
                    score_value=fidelity_score.value,
                    score_sentinel=fidelity_score.sentinel,
                    band="not_measured",
                )
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

        # Apply the deception threshold-driven action ladder. Runs
        # AFTER the jailbreak ladder (jailbreak is single-turn risk;
        # deception is multi-turn additive signal). Risk-precedence is
        # enforced inside the ladder.
        deception_ladder_thresholds = (
            observability_config.deception_thresholds
            if observability_config is not None
            else _DEFAULT_DECEPTION_THRESHOLDS
        )
        result = apply_deception_ladder(
            result, deception_score, deception_ladder_thresholds,
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
            _t0_rehydrate = time.perf_counter()
            _rehydrate_status = "ok"
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
                    if not isinstance(self._rehydration_verifier, NullRehydrationVerifier):
                        _decision_to_outcome = {
                            "accept": "verified",
                            "reject": "rejected",
                            "partial": "partial",
                        }
                        await self._emit_via_ctx(
                            guard_input, RehydrationVerified,
                            verifier_id=type(self._rehydration_verifier).__name__,
                            outcome=_decision_to_outcome.get(verdict.decision, "verified"),
                            rejection_reason=(
                                verdict.reason if verdict.decision == "reject" else None
                            ),
                        )
                except Exception as exc:
                    logger.warning(
                        "Rehydration verifier raised %s — keeping placeholders", exc,
                    )
                    _rehydrate_status = "err"
            await self._emit_via_ctx(
                guard_input, StageRan, stage=STAGE_REHYDRATE,
                duration_ms=(time.perf_counter() - _t0_rehydrate) * 1000,
                status=_rehydrate_status,
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
        # The full DecisionRecord build + emit only fires when the policy
        # router actually ran (``outcome is not None``). On the legacy /
        # pass-through paths we still emit a ``skipped`` StageRan marker so
        # the canvas shows the stage as having been considered, even though
        # no record was built.
        if outcome is None:
            await self._emit_via_ctx(
                guard_input, StageRan, stage=STAGE_DECISION_EMIT,
                duration_ms=0.0,
                status="skipped",
            )
        if outcome is not None:
            _t0_demit = time.perf_counter()
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
            _stage_demit_ev = await self._emit_via_ctx(
                guard_input, StageRan, stage=STAGE_DECISION_EMIT,
                duration_ms=(time.perf_counter() - _t0_demit) * 1000,
                status="ok",
            )
            if _stage_demit_ev is not None:
                await self._emit_via_ctx(
                    guard_input, LifecycleDecisionEmitted,
                    parent_id_override=_stage_demit_ev.id,
                    action=str(result.action),
                    max_risk=outcome_band if outcome_band in ("LOW", "MEDIUM", "HIGH", "CRITICAL") else "LOW",
                    decision_id=decision_id,
                    bypass_reason=result.bypass_reason,
                )

        # --- Middleware after ---
        for mw in self._middlewares:
            try:
                result = await mw.after(result)
            except Exception as exc:
                logger.warning("Middleware.after() raised: %s — using pre-after result", exc)

        # --- Reporter (fire-and-forget, STAGE_REPORT) ---
        # Capture the lifecycle context for the report task so it can emit
        # ReportFlushed without re-walking GuardContext.
        _life_emitter, _life_parent = self._lifecycle_ctx(guard_input)
        asyncio.ensure_future(
            self._fire_report(
                result,
                correlation_id=correlation_id,
                decision_id=decision_id,
                redactor=redactor,
                sampler=sampler,
                lifecycle_emitter=_life_emitter,
                lifecycle_parent_id=_life_parent,
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
        lifecycle_emitter: Any | None = None,
        lifecycle_parent_id: str | None = None,
    ) -> None:
        _t0_report = time.perf_counter()
        _report_status = "ok"
        _failure_count = 0
        try:
            with stage_runner(
                STAGE_REPORT,
                **self._stage_kwargs(correlation_id, decision_id, redactor, sampler),
            ):
                await self._reporter.report(result)
        except Exception as exc:
            logger.warning("Reporter.report() raised: %s", exc)
            _report_status = "err"
            _failure_count = 1
        if lifecycle_emitter is not None:
            try:
                stage_ev = await lifecycle_emitter.emit(
                    StageRan, parent_id=lifecycle_parent_id, stage=STAGE_REPORT,
                    duration_ms=(time.perf_counter() - _t0_report) * 1000,
                    status=_report_status,
                )
                await lifecycle_emitter.emit(
                    ReportFlushed, parent_id=stage_ev.id,
                    reporters=[type(self._reporter).__name__],
                    fanout_count=1,
                    failure_count=_failure_count,
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("LifecycleEmitter.emit() raised in _fire_report: %s", exc)

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
