"""EvaluationHarness Protocol — drives multiple pipeline configurations.

Implementations evaluate a labeled corpus across multiple pipeline
configurations side-by-side and return a ``EvaluationReport`` with
per-configuration metric rows. The harness is single-threaded by
design; operators running configurations in parallel construct
multiple harness instances.

Failure mode: implementations MUST NOT raise outward. Internal
failures are wrapped in ``EvaluationHarnessError`` whose foundation
``__failure_mode__`` is ``closed`` — harness failure means the report
cannot be trusted, so the CLI exits non-zero and writes a
partial-report trail for debugging.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from arc_guard_core.evaluation import (
    Configuration,
    CorpusEntry,
    EvaluationReport,
)


@runtime_checkable
class EvaluationHarness(Protocol):
    """Drive multiple pipeline configurations against a labeled corpus.

    Concurrency: not concurrency-safe; meant for single-threaded
    invocation by the CLI or a test harness.
    Failure mode: implementations MUST NOT raise outward; internal
    failures bubble via ``EvaluationHarnessError`` (foundation
    ``__failure_mode__='closed'``) so the CLI exits non-zero and
    writes a partial-report trail for debugging.
    """

    def evaluate(
        self,
        corpus: Iterable[CorpusEntry],
        configurations: tuple[Configuration, ...],
        *,
        seed: int = 0,
    ) -> EvaluationReport:
        """Drive ``configurations`` against ``corpus`` and return a report."""


__all__ = ["EvaluationHarness"]
