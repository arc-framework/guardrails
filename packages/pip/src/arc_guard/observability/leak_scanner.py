"""Payload-leak scanner for captured observability artifacts.

Pure-function ``scan_for_leaks(captured, *, originals)`` returning a
list of ``LeakReport`` entries. Plain substring search — no regex, no
entropy heuristics. The threshold mirrors
``BoundedRedactor._MIN_SUBSTRING_LENGTH`` so the runtime enforcer and
the CI auditor agree on what counts as a leak.

Used by the contract test suite to scan a captured-artifacts bundle
against the original input text + finding matched substrings, and to
fail CI if any captured emission contains a fragment of the originals.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from arc_guard_core.stages import STAGE_DESCRIPTORS

from arc_guard.observability.recording import (
    CapturedArtifacts,
    CapturedEvent,
    CapturedMetric,
    CapturedSpan,
)

_MIN_SUBSTRING_LENGTH = 4

# Detector / encoder / scorer / verifier IDs follow the documented
# ``<name>:<version>`` shape (e.g. ``"rule-based:1"``,
# ``"sentence-transformers/all-MiniLM-L6-v2:1.0"``, ``"null:1"``). They
# are system-set constants chosen by the SDK or the operator's adapter,
# never derived from user input. The scanner skips values matching
# this shape to avoid false positives when an input prompt happens to
# share a 4+ char substring with a system identifier (e.g. "rule" in
# both "rule-based:1" and the prompt "no rules.").
_SYSTEM_ID_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z][A-Za-z0-9_\-/.]*:[A-Za-z0-9_.\-]+$")


@dataclass(frozen=True)
class LeakReport:
    """One leak finding from the scanner."""

    artifact_kind: str  # "span" | "event" | "metric"
    artifact_name: str
    field_path: str
    matched_original: str
    matched_chunk: str


def _has_chunk(haystack: str, needle: str) -> tuple[bool, str]:
    """Return (True, chunk) if ``haystack`` contains a >= threshold chunk of ``needle``.

    Returns the smallest chunk that matched so the LeakReport can show
    exactly what bled through.
    """
    if len(needle) < _MIN_SUBSTRING_LENGTH:
        return False, ""
    if needle in haystack:
        return True, needle
    for start in range(len(needle) - _MIN_SUBSTRING_LENGTH + 1):
        chunk = needle[start : start + _MIN_SUBSTRING_LENGTH]
        if chunk in haystack:
            return True, chunk
    return False, ""


def _scan_value(
    value: Any,
    *,
    artifact_kind: str,
    artifact_name: str,
    field_path: str,
    originals: tuple[str, ...],
) -> list[LeakReport]:
    # Only scan string values: numeric durations / counts / IDs cannot
    # carry user text, and their string representations produce false
    # positives when they coincidentally share digits with numeric inputs
    # (e.g. a 5.001ms histogram value matches "5.00" in a phone number).
    if not isinstance(value, str):
        return []
    if not value:
        return []
    # The pipeline emits ``stage=<member of STAGE_DESCRIPTORS>`` on
    # every span / event / metric. Stage names are short common English
    # words ("verify", "execute", "report", ...) that legitimately appear
    # in user prompts. Treat exact-match-to-a-known-stage as system-set,
    # not user-derived; otherwise the scanner false-positives whenever
    # an input prompt happens to contain a stage name.
    if value in STAGE_DESCRIPTORS:
        return []
    # System identifiers (detector_id / encoder_id / scorer_id / etc.)
    # follow the documented ``<name>:<version>`` shape. They are chosen
    # by the SDK or operator adapters, never derived from user input.
    # Skip them so the scanner doesn't false-positive when a prompt
    # happens to share a 4+ char chunk with a system identifier.
    if _SYSTEM_ID_PATTERN.fullmatch(value):
        return []
    reports: list[LeakReport] = []
    for original in originals:
        if not original or len(original) < _MIN_SUBSTRING_LENGTH:
            continue
        hit, chunk = _has_chunk(value, original)
        if hit:
            reports.append(
                LeakReport(
                    artifact_kind=artifact_kind,
                    artifact_name=artifact_name,
                    field_path=field_path,
                    matched_original=original,
                    matched_chunk=chunk,
                )
            )
    return reports


def _scan_span(span: CapturedSpan, originals: tuple[str, ...]) -> list[LeakReport]:
    reports: list[LeakReport] = []
    for key, val in span.attributes.items():
        reports.extend(
            _scan_value(
                val,
                artifact_kind="span",
                artifact_name=span.name,
                field_path=f"attributes.{key}",
                originals=originals,
            )
        )
    return reports


def _scan_event(event: CapturedEvent, originals: tuple[str, ...]) -> list[LeakReport]:
    reports: list[LeakReport] = []
    for key, val in event.fields.items():
        reports.extend(
            _scan_value(
                val,
                artifact_kind="event",
                artifact_name=event.name,
                field_path=f"fields.{key}",
                originals=originals,
            )
        )
    return reports


def _scan_metric(metric: CapturedMetric, originals: tuple[str, ...]) -> list[LeakReport]:
    reports: list[LeakReport] = []
    for key, val in metric.attributes.items():
        reports.extend(
            _scan_value(
                val,
                artifact_kind="metric",
                artifact_name=metric.name,
                field_path=f"attributes.{key}",
                originals=originals,
            )
        )
    return reports


def scan_for_leaks(captured: CapturedArtifacts, *, originals: Iterable[str]) -> list[LeakReport]:
    """Scan every captured artifact for fragments of the originals.

    ``originals`` is the input text plus any finding-matched substrings.
    Returns an empty list when the artifacts are clean — the no-leak
    pass condition.
    """
    originals_tuple: tuple[str, ...] = tuple(o for o in originals if o)
    if not originals_tuple:
        return []
    reports: list[LeakReport] = []
    for span in captured.spans:
        reports.extend(_scan_span(span, originals_tuple))
    for event in captured.events:
        reports.extend(_scan_event(event, originals_tuple))
    for metric in captured.metrics:
        reports.extend(_scan_metric(metric, originals_tuple))
    return reports


__all__ = [
    "LeakReport",
    "scan_for_leaks",
]
