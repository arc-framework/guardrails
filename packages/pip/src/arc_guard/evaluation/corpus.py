"""Corpus loader + schema validator.

Loads a Python module exposing a ``CORPUS: tuple[CorpusEntry, ...]``
symbol. Validates each entry against the dataclass shape; accumulates
errors before raising ``CorpusValidationError(code="corpus.entry_invalid")``
listing all offending entries on a single failure.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Iterable
from dataclasses import is_dataclass
from pathlib import Path
from typing import Any

from arc_guard_core.evaluation import CorpusEntry
from arc_guard_core.exceptions import CorpusValidationError

# Path to the bundled labeled corpus. Importable at runtime so
# `tools/run_evaluation.py` can find it without a `tests/`-relative
# install path.
BUNDLED_CORPUS_PATH: Path = (
    Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "adversarial_corpus.py"
)


def load_adversarial_corpus(
    path: Path | None = None,
) -> tuple[CorpusEntry, ...]:
    """Load and validate a labeled corpus from a Python module.

    ``path=None`` loads the bundled corpus from ``BUNDLED_CORPUS_PATH``.
    Otherwise loads from ``path``, which must be a Python module
    exposing a ``CORPUS: tuple[CorpusEntry, ...]`` symbol.

    Raises:
        CorpusValidationError: when the corpus is empty, missing the
            ``CORPUS`` symbol, or contains malformed entries. All
            offending entries are listed in ``details["errors"]`` so
            curators can fix multiple issues in one pass.
    """
    target = path if path is not None else BUNDLED_CORPUS_PATH
    if not target.exists():
        raise CorpusValidationError(
            f"corpus path does not exist: {target}",
            code="corpus.schema_mismatch",
        )

    spec = importlib.util.spec_from_file_location(
        f"_arc_guard_corpus_{abs(hash(str(target)))}",
        target,
    )
    if spec is None or spec.loader is None:
        raise CorpusValidationError(
            f"could not load corpus module from: {target}",
            code="corpus.schema_mismatch",
        )
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover — defensive
        raise CorpusValidationError(
            f"corpus module failed to import: {exc}",
            code="corpus.schema_mismatch",
            cause=exc,
        ) from exc

    if not hasattr(module, "CORPUS"):
        raise CorpusValidationError(
            "corpus module must expose a CORPUS: tuple[CorpusEntry, ...] symbol",
            code="corpus.schema_mismatch",
        )

    raw: Any = module.CORPUS
    if not isinstance(raw, Iterable):
        raise CorpusValidationError(
            "CORPUS must be iterable",
            code="corpus.schema_mismatch",
        )

    entries: list[CorpusEntry] = []
    errors: list[str] = []
    for index, entry in enumerate(raw):
        if not is_dataclass(entry) or not isinstance(entry, CorpusEntry):
            errors.append(f"entry {index}: not a CorpusEntry instance (got {type(entry).__name__})")
            continue
        # Validation already ran in CorpusEntry.__post_init__ at
        # construction time; re-validation here is defensive — if a
        # custom subclass somehow bypassed __post_init__ we would
        # detect missing fields by reflection here, but for now the
        # dataclass instance is trusted.
        entries.append(entry)

    if errors:
        raise CorpusValidationError(
            f"corpus has {len(errors)} invalid entries",
            code="corpus.entry_invalid",
            details={"errors": tuple(errors)},
        )

    if not entries:
        raise CorpusValidationError(
            "corpus is empty",
            code="corpus.empty",
        )

    return tuple(entries)


__all__ = [
    "load_adversarial_corpus",
    "BUNDLED_CORPUS_PATH",
]
