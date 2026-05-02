"""GuardConfig — immutable structural settings for the arc-guard pipeline.

Separation of concerns:
    GuardConfig = WHAT to load (structural settings: models, entity lists, paths).
    FlagProvider = HOW to behave (runtime knobs: enabled, lite_mode, action_strategy).
    FlagProvider always wins for shared behavioral keys.
"""

from __future__ import annotations

import os
from pathlib import Path

from arc_guard_core.observability_config import ObservabilityConfig
from pydantic import BaseModel, ConfigDict, Field, field_validator


class GuardConfig(BaseModel):
    """Immutable structural configuration for GuardPipeline.

    Do NOT add behavioral flags here (enabled, lite_mode, action_strategy).
    Those belong in FlagProvider.
    """

    model_config = ConfigDict(frozen=True)

    # Observability + fidelity-threshold knobs. Optional so the
    # default pipeline keeps its existing fast path (no redactor / no
    # buffered sampler). When set, the pipeline reads
    # ``observability.fidelity_thresholds`` to drive the action ladder
    # and activates the redactor / sampler / log-level floor.
    observability: ObservabilityConfig | None = Field(default=None)

    # PII entity types passed to presidio-analyzer
    pii_entities: list[str] = [
        "CREDIT_CARD",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "PERSON",
        "IBAN_CODE",
        "US_SSN",
        "US_PASSPORT",
        "IP_ADDRESS",
    ]

    # Language for presidio-analyzer (non-English needs the matching spacy model)
    language: str = "en"

    # Path to a pre-downloaded distilbert model directory (for air-gap / offline use).
    # If None, transformers uses GUARD_MODEL_CACHE_DIR or the default HuggingFace cache.
    model_path: Path | None = None

    # Base directory for the HuggingFace model cache.
    # Defaults to ~/.cache/arc/models/
    model_cache_dir: Path = Path.home() / ".cache" / "arc" / "models"

    @field_validator("language")
    @classmethod
    def _language_lowercase(cls, v: str) -> str:
        return v.lower()

    @classmethod
    def from_env(cls, prefix: str = "GUARD_") -> GuardConfig:
        """Construct from environment variables.

        Recognised variables (all optional):
            GUARD_PII_ENTITIES  — comma-separated entity names
            GUARD_LANGUAGE      — ISO 639-1 language code (default: "en")
            GUARD_MODEL_PATH    — absolute path to pre-downloaded model dir
            GUARD_MODEL_CACHE_DIR — base dir for HuggingFace model cache
        """
        # Build each field explicitly so mypy can verify the types
        pii_entities: list[str] | None = None
        language: str | None = None
        model_path: Path | None = None
        model_cache_dir: Path | None = None

        raw_entities = os.environ.get(f"{prefix}PII_ENTITIES", "")
        if raw_entities:
            pii_entities = [e.strip() for e in raw_entities.split(",") if e.strip()]

        lang_val = os.environ.get(f"{prefix}LANGUAGE", "")
        if lang_val:
            language = lang_val

        model_path_str = os.environ.get(f"{prefix}MODEL_PATH", "")
        if model_path_str:
            model_path = Path(model_path_str)

        cache_dir_str = os.environ.get(f"{prefix}MODEL_CACHE_DIR", "")
        if cache_dir_str:
            model_cache_dir = Path(cache_dir_str)

        instance = cls()
        # Use model_copy to apply only the env-provided overrides (frozen model pattern)
        overrides: dict[str, list[str] | str | Path] = {}
        if pii_entities is not None:
            overrides["pii_entities"] = pii_entities
        if language is not None:
            overrides["language"] = language
        if model_path is not None:
            overrides["model_path"] = model_path
        if model_cache_dir is not None:
            overrides["model_cache_dir"] = model_cache_dir
        return instance.model_copy(update=overrides) if overrides else instance
