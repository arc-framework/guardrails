"""SqlInjectionInspector — detects SQL injection patterns in inspected text.

Uses ``sqlparse`` for grammar-aware tokenization so documentation
snippets that mention SQL keywords without a stacked-statement structure
do not produce false positives. Three subtypes are surfaced:

- ``sql.stacked_statement`` — multiple top-level statements where each
  side parses as a real SQL command (DML / DDL keyword leading the
  statement), so prose containing an embedded ``;`` does not trigger.
- ``sql.comment_terminator`` — inline ``--`` or ``/* ... */`` immediately
  following a SQL keyword that the model would otherwise execute.
- ``sql.union_injection`` — a ``UNION SELECT`` token sequence appearing
  after another ``SELECT``.

The inspector is opt-in (the operator must include it in
``GuardPipeline(inspectors=...)``); by default it only fires on the
``post_process`` phase to match the data-flowing-into-tools threat model.
Operators wanting to scan model input as well pass ``phases=`` covering
both phases at construction time.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

from arc_guard_core.exceptions import ConfigSchemaError
from arc_guard_core.observability import Logger, NullLogger
from arc_guard_core.types import Finding, GuardResult

from arc_guard.inspectors.code_injection._common import (
    build_code_injection_finding,
    closed_posture_inspect,
)

_DEFAULT_PHASES = frozenset({"post_process"})

# Statements whose first significant token is one of these keywords are
# treated as "real" SQL for stacked-statement disambiguation. The list
# intentionally excludes ``UNION`` (subordinate clause, not a leading
# statement keyword) and includes the common DML / DDL set the inspector
# must guard.
_LEADING_SQL_KEYWORDS = frozenset({
    "select",
    "insert",
    "update",
    "delete",
    "drop",
    "create",
    "alter",
    "truncate",
    "merge",
    "replace",
    "grant",
    "revoke",
    "exec",
    "execute",
    "call",
})

_COMMENT_TERMINATOR_RE = re.compile(
    r"(?P<keyword>\b(?:select|insert|update|delete|drop|create|alter|truncate|"
    r"merge|replace|grant|revoke|exec|execute|call)\b)"
    r"[^\n;]{0,200}?"
    r"(?P<comment>--[^\n]*|/\*.*?\*/)",
    re.IGNORECASE | re.DOTALL,
)

_UNION_INJECTION_RE = re.compile(
    r"\bselect\b.+?\b(?P<union>union(?:\s+all)?\s+select)\b",
    re.IGNORECASE | re.DOTALL,
)


class SqlInjectionInspector:
    """Inspector that flags SQL-injection-shaped patterns in the inspected text."""

    name: str = "SqlInjectionInspector"

    def __init__(
        self,
        *,
        capture_raw_matches: bool = False,
        max_input_chars: int = 1_000_000,
        phases: Iterable[str] = _DEFAULT_PHASES,
        logger: Logger | None = None,
    ) -> None:
        if max_input_chars <= 0:
            raise ConfigSchemaError(
                "SqlInjectionInspector: max_input_chars must be > 0",
                code="config.type_mismatch",
                details={"field": "max_input_chars"},
            )
        self._capture_raw_matches = bool(capture_raw_matches)
        self._max_input_chars = int(max_input_chars)
        self._phases = frozenset(phases)
        self._logger: Logger = logger or NullLogger()
        # Surface stdlib-logger warnings via this fallback as well so
        # operators using either observability path see the same events.
        self._py_logger = logging.getLogger(__name__)

    @closed_posture_inspect
    async def inspect(self, result: GuardResult) -> GuardResult:
        if result.phase not in self._phases:
            return result

        text = result.text
        if len(text) > self._max_input_chars:
            self._emit_unparseable("size_limit", len(text))
            return result

        try:
            import sqlparse  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ConfigSchemaError(
                "SqlInjectionInspector requires the [code-injection] extra: "
                "pip install arc-guard[code-injection]",
                code="config.missing_field",
                details={"extra": "code-injection"},
            ) from exc

        try:
            statements = sqlparse.parse(text)
        except Exception:
            self._emit_unparseable("parse_error", len(text))
            return result

        if not statements:
            self._emit_unparseable("empty_parse", len(text))
            return result

        new_findings: list[Finding] = list(result.findings)
        new_findings.extend(self._detect_stacked(text, statements))
        new_findings.extend(self._detect_comment_terminator(text))
        new_findings.extend(self._detect_union(text))

        if len(new_findings) == len(result.findings):
            return result

        return GuardResult(
            text=result.text,
            action=result.action,
            findings=tuple(new_findings),
            bypass_reason=result.bypass_reason,
            phase=result.phase,
        )

    # ------------------------------------------------------------------
    # Detectors
    # ------------------------------------------------------------------

    def _detect_stacked(
        self, text: str, statements: tuple[object, ...]
    ) -> list[Finding]:
        if len(statements) < 2:
            return []

        sql_like_count = sum(
            1
            for stmt in statements
            if _leading_keyword(str(stmt)) in _LEADING_SQL_KEYWORDS
        )
        if sql_like_count < 2:
            return []

        # Span: from the start of the second SQL-like statement to its end.
        # sqlparse does not expose offsets directly, so we reconstruct the
        # offset by walking through the sub-statements in input order.
        offset = 0
        first_real_index: int | None = None
        for idx, stmt in enumerate(statements):
            stmt_text = str(stmt)
            if _leading_keyword(stmt_text) in _LEADING_SQL_KEYWORDS:
                if first_real_index is None:
                    first_real_index = idx
                elif idx > first_real_index:
                    span_start = offset
                    span_end = offset + len(stmt_text)
                    raw = text[span_start:span_end]
                    return [
                        build_code_injection_finding(
                            inspector_name=self.name,
                            subtype="sql.stacked_statement",
                            span=(span_start, span_end),
                            raw_text=raw,
                            capture_raw_matches=self._capture_raw_matches,
                        )
                    ]
            offset += len(stmt_text)
        return []

    def _detect_comment_terminator(self, text: str) -> list[Finding]:
        out: list[Finding] = []
        for match in _COMMENT_TERMINATOR_RE.finditer(text):
            comment_start = match.start("comment")
            comment_end = match.end("comment")
            raw = text[comment_start:comment_end]
            out.append(
                build_code_injection_finding(
                    inspector_name=self.name,
                    subtype="sql.comment_terminator",
                    span=(comment_start, comment_end),
                    raw_text=raw,
                    capture_raw_matches=self._capture_raw_matches,
                )
            )
        return out

    def _detect_union(self, text: str) -> list[Finding]:
        out: list[Finding] = []
        for match in _UNION_INJECTION_RE.finditer(text):
            union_start = match.start("union")
            union_end = match.end("union")
            raw = text[union_start:union_end]
            out.append(
                build_code_injection_finding(
                    inspector_name=self.name,
                    subtype="sql.union_injection",
                    span=(union_start, union_end),
                    raw_text=raw,
                    capture_raw_matches=self._capture_raw_matches,
                )
            )
        return out

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def _emit_unparseable(self, reason: str, size: int) -> None:
        self._logger.event(
            "guard.code_injection.unparseable_input",
            level="warning",
            inspector=self.name,
            reason=reason,
            input_size=size,
        )
        self._py_logger.warning(
            "guard.code_injection.unparseable_input",
            extra={
                "inspector": self.name,
                "reason": reason,
                "input_size": size,
            },
        )


def _leading_keyword(text: str) -> str:
    stripped = text.lstrip().lower()
    if not stripped:
        return ""
    head = stripped.split(None, 1)[0] if stripped else ""
    # Strip a trailing punctuation glyph so e.g. "select(" or "select;"
    # still hits the keyword list.
    return "".join(ch for ch in head if ch.isalpha())


__all__ = ["SqlInjectionInspector"]
