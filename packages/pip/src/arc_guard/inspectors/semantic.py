"""SemanticInspector — distilbert intent classifier for toxic/injection detection."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from arc_guard_core.protocols.flag_provider import FlagProvider
from arc_guard_core.types import Finding, GuardResult, RiskLevel

from arc_guard.config_env import GuardConfig

_LOG = logging.getLogger(__name__)

_DEFAULT_MODEL_NAME = "distilbert-base-uncased-finetuned-sst-2-english"

_LABEL_TO_ENTITY: dict[str, str] = {
    "TOXIC": "TOXIC",
    "INJECTION": "INJECTION",
    # SST-2 labels — map negative sentiment as TOXIC
    "NEGATIVE": "TOXIC",
    "LABEL_0": "TOXIC",
}


class SemanticInspector:
    """DistilBERT-based intent classifier for toxic output and injection detection.

    Runs inference in a thread pool executor to avoid blocking the event loop.

    Args:
        config: GuardConfig providing model_path and model_cache_dir.
        flag_provider: Runtime flag source for threshold overrides.
    """

    def __init__(self, config: GuardConfig, flag_provider: FlagProvider) -> None:
        try:
            from transformers import pipeline  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "transformers is required for SemanticInspector. "
                "Install it with: pip install arc-guard[semantic]"
            ) from exc

        self._flag_provider = flag_provider

        model_name = os.environ.get("GUARD_SEMANTIC_MODEL_NAME", _DEFAULT_MODEL_NAME)

        if config.model_path is not None:
            model_source: str | Any = str(config.model_path)
        else:
            os.environ["TRANSFORMERS_CACHE"] = str(config.model_cache_dir)
            model_source = model_name

        self._pipeline = pipeline("text-classification", model=model_source)

    async def inspect(self, result: GuardResult) -> GuardResult:
        """Run semantic classification against the result text.

        Uses a thread pool executor so the event loop is never blocked.
        Never raises — all exceptions are caught internally.
        """
        try:
            text = result.text
            if not text.strip():
                return result

            threshold_key = (
                "semantic_input_threshold"
                if result.phase == "pre_process"
                else "semantic_output_threshold"
            )
            raw_threshold = self._flag_provider.get_string(threshold_key, "0.85")
            try:
                threshold = float(raw_threshold)
            except ValueError:
                threshold = 0.85

            loop = asyncio.get_event_loop()
            predictions: list[dict[str, Any]] = await loop.run_in_executor(
                None, self._infer, text
            )

            new_findings = list(result.findings)

            for pred in predictions:
                label: str = pred.get("label", "")
                score: float = float(pred.get("score", 0.0))

                if score < threshold:
                    continue

                entity_type = _LABEL_TO_ENTITY.get(label.upper(), label.upper())

                new_findings.append(
                    Finding(
                        entity_type=entity_type,
                        start=0,
                        end=len(text),
                        risk_level=RiskLevel.HIGH,
                        inspector="semantic",
                        score=score,
                    )
                )

            if len(new_findings) == len(result.findings):
                return result

            return GuardResult(
                text=result.text,
                action=result.action,
                findings=tuple(new_findings),
                bypass_reason=result.bypass_reason,
                phase=result.phase,
            )
        except Exception:
            _LOG.exception("SemanticInspector encountered an unexpected error")
            return result

    def _infer(self, text: str) -> list[dict[str, Any]]:
        """Run the transformers pipeline synchronously (called in executor)."""
        raw: Any = self._pipeline(text)
        if isinstance(raw, list) and len(raw) > 0 and isinstance(raw[0], dict):
            return list(raw)
        return []
