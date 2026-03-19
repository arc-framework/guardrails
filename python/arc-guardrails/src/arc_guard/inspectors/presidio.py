"""PresidioInspector — PII/PCI detector via presidio-analyzer."""

from __future__ import annotations

import logging
from typing import Any

from arc_guard.config import GuardConfig
from arc_guard.types import Finding, GuardResult, RiskLevel

_LOG = logging.getLogger(__name__)


def _score_to_risk(score: float) -> RiskLevel:
    if score >= 0.85:
        return RiskLevel.HIGH
    if score >= 0.6:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


class PresidioInspector:
    """PII and PCI detector backed by presidio-analyzer.

    Args:
        config: GuardConfig supplying the entity list and language.
        engine: Injectable AnalyzerEngine for unit testing. If None, a default
            engine is created at construction time.
        extra_recognizers: Optional additional PatternRecognizer instances to
            add to the engine's registry before first use.
    """

    def __init__(
        self,
        config: GuardConfig,
        engine: Any | None = None,
        extra_recognizers: list[Any] | None = None,
    ) -> None:
        try:
            from presidio_analyzer import AnalyzerEngine
        except ImportError as exc:
            raise ImportError(
                "presidio-analyzer is required for PresidioInspector. "
                "Install it with: pip install presidio-analyzer"
            ) from exc

        self._config = config
        self._entities = config.pii_entities
        self._language = config.language

        if engine is not None:
            self._engine: Any = engine
        else:
            self._engine = AnalyzerEngine()

        if extra_recognizers:
            registry = self._engine.registry
            for recognizer in extra_recognizers:
                registry.add_recognizer(recognizer)

    async def inspect(self, result: GuardResult) -> GuardResult:
        """Detect PII/PCI entities in the result text using presidio-analyzer.

        Appends a Finding for each recognized entity. Never raises.
        """
        try:
            text = result.text
            ctx_source = "input" if result.phase == "pre_process" else "output"

            presidio_results = self._engine.analyze(
                text=text,
                entities=self._entities,
                language=self._language,
            )

            if not presidio_results:
                return result

            new_findings = list(result.findings)

            for pr in presidio_results:
                risk = _score_to_risk(pr.score)
                new_findings.append(
                    Finding(
                        entity_type=pr.entity_type,
                        start=pr.start,
                        end=pr.end,
                        risk_level=risk,
                        inspector="presidio",
                        score=pr.score,
                        metadata={"source": ctx_source},
                    )
                )

            return GuardResult(
                text=result.text,
                action=result.action,
                findings=tuple(new_findings),
                bypass_reason=result.bypass_reason,
                phase=result.phase,
            )
        except Exception:
            _LOG.exception("PresidioInspector encountered an unexpected error")
            return result
