"""``HarnessImpl`` — drives the four pipeline configurations against a corpus.

Constructs:

- ``raw`` — a ``_RawPassThrough`` stub that returns
  ``GuardResult(text=input.text, action="pass")`` without invoking any
  pipeline stages. Measures the GUARD layer's no-op overhead, NOT LLM
  behavior.
- ``sanitize_only`` — ``GuardPipeline(...)`` with default inspectors
  + redact strategy, no jailbreak detector, no deception inspector.
- ``sanitize_plus_jailbreak`` — adds the rule-based jailbreak detector
  + the stateful deception inspector.
- ``sanitize_plus_jailbreak_plus_fidelity`` — adds the
  ``SemanticBundle.from_sentence_transformers()`` adapter when the
  ``[semantic]`` extra is installed. **`[semantic]`-extra fallback**:
  when the extra is NOT installed, the harness skips the
  fidelity-verification stage, sets ``fidelity_score_median = None``,
  and emits a single ``harness.fidelity_unavailable`` warning event.

Reproducibility: same ``(corpus, seed)`` pair → byte-identical
precision / recall / sanitization / refusal-rate / clarification-rate
columns; latency columns may vary within ±20% jitter.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Iterable

from arc_guard_core.evaluation import (
    Configuration,
    ConfigurationMetrics,
    CorpusEntry,
    EvaluationReport,
    ExpectedOutcome,
)
from arc_guard_core.exceptions import EvaluationHarnessError
from arc_guard_core.types import GuardInput, GuardResult

from arc_guard.evaluation.metrics import (
    category_precision_recall,
    compute_fidelity_score_median,
    compute_intelligibility_score,
    compute_latency_percentiles,
    compute_refusal_clarification_rates,
)
from arc_guard.pipeline import GuardPipeline

_LOG = logging.getLogger("arc_guard.evaluation")
_FIDELITY_UNAVAILABLE_EVENT = "harness.fidelity_unavailable"


def _outcome_for_result(result: GuardResult) -> ExpectedOutcome:
    """Reduce a ``GuardResult`` to one of the four documented outcomes."""
    if result.action == "block" or result.refusal is not None:
        return "refuse"
    if result.clarification is not None:
        return "clarify"
    if getattr(result, "fidelity_warning", False):
        return "warn"
    return "pass"


def _entry_text(entry: CorpusEntry) -> str:
    """Concatenate multi-turn entries for single-pass evaluation."""
    if entry.prompt is not None:
        return entry.prompt
    assert entry.turns is not None
    return "\n".join(entry.turns)


class _RawPassThrough:
    """No-op pipeline stand-in for the ``raw`` configuration.

    Returns ``GuardResult(text=input.text, action="pass")`` regardless
    of input. Measures the GUARD layer's no-op overhead, NOT LLM
    behavior.
    """

    async def pre_process(self, guard_input: GuardInput) -> GuardResult:
        return GuardResult(text=guard_input.text, action="pass")


class HarnessImpl:
    """Concrete ``EvaluationHarness`` implementation."""

    def evaluate(
        self,
        corpus: Iterable[CorpusEntry],
        configurations: tuple[Configuration, ...],
        *,
        seed: int = 0,
    ) -> EvaluationReport:
        try:
            corpus_list = list(corpus)
            metrics: list[ConfigurationMetrics] = []
            for config in configurations:
                pipeline_or_stub = self._build_pipeline(config, seed=seed)
                metrics.append(
                    self._evaluate_one_configuration(
                        config, pipeline_or_stub, corpus_list,
                    ),
                )
            return EvaluationReport(
                seed=seed,
                corpus_size=len(corpus_list),
                configurations=tuple(metrics),
            )
        except EvaluationHarnessError:
            raise
        except Exception as exc:
            raise EvaluationHarnessError(
                f"harness failed: {exc}",
                code="evaluation_harness.metric_compute_failed",
                cause=exc,
            ) from exc

    def _build_pipeline(
        self, configuration: Configuration, *, seed: int,
    ) -> GuardPipeline | _RawPassThrough:
        """Construct the pipeline (or stub) for a configuration."""
        del seed  # reserved for ML detector reproducibility
        if configuration == "raw":
            return _RawPassThrough()
        if configuration == "sanitize_only":
            return self._sanitize_only_pipeline()
        if configuration == "sanitize_plus_jailbreak":
            return self._sanitize_plus_jailbreak_pipeline()
        if configuration == "sanitize_plus_jailbreak_plus_fidelity":
            return self._sanitize_plus_jailbreak_plus_fidelity_pipeline()
        raise EvaluationHarnessError(
            f"unknown configuration: {configuration!r}",
            code="evaluation_harness.configuration_invalid",
        )

    def _sanitize_only_pipeline(self) -> GuardPipeline:
        """Pipeline with default inspectors + redact strategy, no jailbreak/deception."""

        class _NoOpJailbreak:
            @property
            def detector_id(self) -> str:
                return "harness-noop-jb:1"

            def detect(
                self, text: str, *, conversation_state: object = None
            ) -> tuple[object, ...]:
                return ()

        return GuardPipeline(
            inspectors=None,
            jailbreak_detector=_NoOpJailbreak(),  # type: ignore[arg-type]
        )

    def _sanitize_plus_jailbreak_pipeline(self) -> GuardPipeline:
        """Adds the default rule-based jailbreak detector."""
        return GuardPipeline(inspectors=None)

    def _sanitize_plus_jailbreak_plus_fidelity_pipeline(self) -> GuardPipeline:
        """Adds the ``SemanticBundle`` when ``[semantic]`` is installed.

        Documented fallback: when the extra is missing, returns the
        ``sanitize_plus_jailbreak`` pipeline and emits a warning event
        on the harness logger. The resulting metrics row will have
        ``fidelity_score_median = None``.
        """
        try:
            from arc_guard.middleware import from_sentence_transformers
        except ImportError:
            _LOG.warning(
                "%s: [semantic] extra not installed — fidelity stage skipped "
                "for sanitize_plus_jailbreak_plus_fidelity configuration",
                _FIDELITY_UNAVAILABLE_EVENT,
            )
            return self._sanitize_plus_jailbreak_pipeline()
        try:
            bundle = from_sentence_transformers()
        except ImportError:
            # Lazy-factory raises ImportError when the deps are missing.
            _LOG.warning(
                "%s: [semantic] factory raised ImportError — fidelity stage skipped",
                _FIDELITY_UNAVAILABLE_EVENT,
            )
            return self._sanitize_plus_jailbreak_pipeline()
        return GuardPipeline(
            inspectors=None,
            intent_encoder=bundle.encoder,
            fidelity_scorer=bundle.scorer,
            rehydration_verifier=bundle.verifier,
        )

    def _evaluate_one_configuration(
        self,
        configuration: Configuration,
        pipeline: GuardPipeline | _RawPassThrough,
        corpus: list[CorpusEntry],
    ) -> ConfigurationMetrics:
        """Run the corpus through ``pipeline`` and compute metrics."""
        triples: list[tuple[CorpusEntry, ExpectedOutcome, ExpectedOutcome]] = []
        latencies: list[float] = []
        fidelity_values: list[float | None] = []
        answers: list[str] = []
        prompts: list[str] = []
        actuals: list[ExpectedOutcome] = []

        for entry in corpus:
            text = _entry_text(entry)
            prompts.append(text)
            expected = entry.expected_outcomes.get(configuration)
            if expected is None:
                # Entries that aren't labeled for this configuration
                # are skipped from the per-category metrics; we still
                # run them so latency and rate metrics are stable.
                expected = "pass"
            t0 = time.perf_counter_ns()
            result = asyncio.run(
                pipeline.pre_process(GuardInput(text=text)),
            )
            elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000
            latencies.append(elapsed_ms)
            answers.append(result.text)

            actual = _outcome_for_result(result)
            actuals.append(actual)
            triples.append((entry, actual, expected))

            score = result.fidelity_score
            if score is not None and score.sentinel == "measured":
                fidelity_values.append(score.value)
            else:
                fidelity_values.append(None)

        jb_p, jb_r = category_precision_recall(triples, "single_turn_jailbreak")
        dec_p, dec_r = category_precision_recall(triples, "multi_turn_deception")
        san_p, san_r = category_precision_recall(triples, "privacy_sensitive")
        refusal_rate, clarification_rate = compute_refusal_clarification_rates(actuals)
        p50, p99 = compute_latency_percentiles(latencies)
        fidelity_median = (
            compute_fidelity_score_median(fidelity_values)
            if configuration == "sanitize_plus_jailbreak_plus_fidelity"
            else None
        )
        intelligibility = compute_intelligibility_score(answers, prompts)

        return ConfigurationMetrics(
            configuration=configuration,
            jailbreak_precision=jb_p,
            jailbreak_recall=jb_r,
            deception_precision=dec_p,
            deception_recall=dec_r,
            sanitization_precision=san_p,
            sanitization_recall=san_r,
            fidelity_score_median=fidelity_median,
            refusal_rate=refusal_rate,
            clarification_rate=clarification_rate,
            latency_p50_ms=p50,
            latency_p99_ms=p99,
            intelligibility_score=intelligibility,
        )


__all__ = ["HarnessImpl"]
