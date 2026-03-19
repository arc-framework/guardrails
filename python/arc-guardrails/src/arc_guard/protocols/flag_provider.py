"""FlagProvider protocol — runtime behavioral knobs for the pipeline."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class FlagProvider(Protocol):
    """Runtime feature-flag interface.

    FlagProvider controls *how* the pipeline behaves at runtime.
    GuardConfig controls *what* gets loaded structurally.
    FlagProvider always wins when both express the same key.

    Standard flag keys used by GuardPipeline:
        enabled              — bool: whether the guard runs at all
        lite_mode            — bool: skip SemanticInspector (latency-sensitive paths)
        action_strategy      — str: "redact" | "hash" | "block" (default: "redact")
        injection_enabled    — bool: whether InjectionInspector runs
        semantic_input_threshold  — str float: minimum score for input detections
        semantic_output_threshold — str float: minimum score for output detections
    """

    def is_enabled(self, flag: str, default: bool = False) -> bool:
        """Return the boolean value of *flag*."""
        ...

    def get_string(self, flag: str, default: str = "") -> str:
        """Return the string value of *flag*."""
        ...

    def get_list(self, flag: str, default: list[str] | None = None) -> list[str]:
        """Return a list of strings for *flag* (comma-separated in env form)."""
        ...
