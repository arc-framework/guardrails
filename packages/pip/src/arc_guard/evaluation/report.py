"""Evaluation report writers.

- ``write_jsonl`` — one JSON line per ``ConfigurationMetrics`` row.
- ``write_markdown`` — Markdown summary table with all documented columns.

Column ordering is stable across calls; output is byte-identical for
identical input reports (numeric formatting is fixed).
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

from arc_guard_core.evaluation import EvaluationReport

# Stable column ordering (header → field name).
_COLUMNS: tuple[tuple[str, str], ...] = (
    ("Configuration", "configuration"),
    ("Jailbreak P", "jailbreak_precision"),
    ("Jailbreak R", "jailbreak_recall"),
    ("Deception P", "deception_precision"),
    ("Deception R", "deception_recall"),
    ("Sanitization P", "sanitization_precision"),
    ("Sanitization R", "sanitization_recall"),
    ("Fidelity Median", "fidelity_score_median"),
    ("Refusal Rate", "refusal_rate"),
    ("Clarification Rate", "clarification_rate"),
    ("Latency p50 (ms)", "latency_p50_ms"),
    ("Latency p99 (ms)", "latency_p99_ms"),
    ("Intelligibility", "intelligibility_score"),
)


def write_jsonl(report: EvaluationReport, path: Path) -> None:
    """Write the report as JSON Lines (one configuration per line).

    The first line is a header with seed and corpus_size; subsequent
    lines are per-configuration metric rows. This format is the
    machine-readable pair to ``write_markdown``'s human-readable
    summary.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        header = {"kind": "header", "seed": report.seed, "corpus_size": report.corpus_size}
        fh.write(json.dumps(header, sort_keys=True) + "\n")
        for row in report.configurations:
            payload: dict[str, Any] = dataclasses.asdict(row)
            payload["kind"] = "configuration"
            fh.write(json.dumps(payload, sort_keys=True) + "\n")


def _format_value(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def write_markdown(report: EvaluationReport, path: Path) -> None:
    """Write a Markdown summary table with all documented columns.

    Stable column order; numeric formatting fixed at 3 decimal places
    so output is byte-identical for identical input.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append(f"# Evaluation Report (seed={report.seed}, corpus_size={report.corpus_size})")
    lines.append("")
    headers = [header for header, _ in _COLUMNS]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in report.configurations:
        cells: list[str] = []
        for _, field_name in _COLUMNS:
            value = getattr(row, field_name)
            cells.append(_format_value(value))
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


__all__ = ["write_jsonl", "write_markdown"]
