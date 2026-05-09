#!/usr/bin/env python3
"""CLI entrypoint for the comparative evaluation harness.

Drives the harness against an operator-provided corpus path or the
bundled corpus, writes a JSON Lines report + Markdown summary to the
output directory, and exits non-zero on harness or corpus-validation
errors.

Usage:

    tools/run_evaluation.py [--corpus PATH] [--configurations LIST]
                            [--seed N] [--output-dir PATH]

Defaults: bundled corpus, all four configurations, seed=0,
``./evaluation_output/``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from arc_guard_core.evaluation import Configuration
from arc_guard_core.exceptions import CorpusValidationError, EvaluationHarnessError

from arc_guard.evaluation import (
    HarnessImpl,
    load_adversarial_corpus,
    write_jsonl,
    write_markdown,
)

_LOG = logging.getLogger("arc_guard.evaluation.cli")

_ALL_CONFIGURATIONS: tuple[Configuration, ...] = (
    "raw",
    "sanitize_only",
    "sanitize_plus_jailbreak",
    "sanitize_plus_jailbreak_plus_fidelity",
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Drive the comparative evaluation harness against a labeled corpus "
            "and write a JSON Lines report + Markdown summary."
        ),
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=None,
        help="Path to a Python module exposing a CORPUS: tuple[CorpusEntry, ...] symbol. "
             "Defaults to the bundled corpus.",
    )
    parser.add_argument(
        "--configurations",
        type=str,
        default=",".join(_ALL_CONFIGURATIONS),
        help=(
            "Comma-separated list of configurations to evaluate. "
            f"Allowed: {', '.join(_ALL_CONFIGURATIONS)}. "
            "Defaults to all four."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Deterministic seed for reproducibility. Defaults to 0.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation_output"),
        help="Directory to write report.jsonl + report.md into. "
             "Defaults to ./evaluation_output/.",
    )
    return parser.parse_args(argv)


def _validate_configurations(raw: str) -> tuple[Configuration, ...]:
    requested = [c.strip() for c in raw.split(",") if c.strip()]
    invalid = [c for c in requested if c not in _ALL_CONFIGURATIONS]
    if invalid:
        raise SystemExit(
            f"unknown configurations: {invalid!r}. "
            f"Allowed: {', '.join(_ALL_CONFIGURATIONS)}"
        )
    return tuple(requested)  # type: ignore[return-value]


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _parse_args(argv)
    configurations = _validate_configurations(args.configurations)

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    error_log = output_dir / "error.log"

    try:
        corpus = load_adversarial_corpus(args.corpus)
    except CorpusValidationError as exc:
        _LOG.error("corpus validation failed: %s", exc)
        error_log.write_text(f"corpus validation failed: {exc}\n", encoding="utf-8")
        return 2

    try:
        harness = HarnessImpl()
        report = harness.evaluate(
            corpus=corpus,
            configurations=configurations,
            seed=args.seed,
        )
    except EvaluationHarnessError as exc:
        _LOG.error("harness failed: %s", exc)
        error_log.write_text(f"harness failed: {exc}\n", encoding="utf-8")
        return 3

    write_jsonl(report, output_dir / "report.jsonl")
    write_markdown(report, output_dir / "report.md")
    _LOG.info(
        "evaluation complete: %d configurations × %d corpus entries → %s",
        len(report.configurations), report.corpus_size, output_dir,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
