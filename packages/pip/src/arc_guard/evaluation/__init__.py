"""Evaluation sub-package: harness implementation, corpus loader, metrics, report writer.

Drives multiple pipeline configurations against a labeled corpus and
emits a reproducible comparison report. Used by `tools/run_evaluation.py`
for the dissertation-quality empirical claims.
"""

from __future__ import annotations

from arc_guard.evaluation.corpus import (
    BUNDLED_CORPUS_PATH,
    load_adversarial_corpus,
)
from arc_guard.evaluation.harness import HarnessImpl
from arc_guard.evaluation.report import write_jsonl, write_markdown

__all__ = [
    "HarnessImpl",
    "load_adversarial_corpus",
    "BUNDLED_CORPUS_PATH",
    "write_jsonl",
    "write_markdown",
]
