"""ShellInjectionInspector — detects shell injection patterns.

Uses a small state machine that mirrors POSIX shell quoting rules so
metacharacters appearing inside single quotes, double quotes, or after
a backslash are not flagged. Three subtypes are surfaced:

- ``shell.command_substitution`` — ``$(...)`` or backtick substitution at
  an unquoted position.
- ``shell.pipe_into_destructive`` — ``|`` immediately followed by a
  destructive command (``rm``, ``dd``, ``mkfs``) or by the append-
  redirect form ``>>``.
- ``shell.command_chaining`` — ``;``, ``&&``, or ``||`` at an unquoted
  position.

The inspector relies on stdlib ``shlex`` only as a sanity check; the
quote-aware scan is the source of truth for offsets so spans line up
with the underlying text.
"""

from __future__ import annotations

import logging
import re
import shlex
from collections.abc import Iterable

from arc_guard_core.exceptions import ConfigSchemaError
from arc_guard_core.observability import Logger, NullLogger
from arc_guard_core.types import Finding, GuardResult

from arc_guard.inspectors.code_injection._common import (
    build_code_injection_finding,
    closed_posture_inspect,
)

_DEFAULT_PHASES = frozenset({"post_process"})

_DESTRUCTIVE_PIPE_RE = re.compile(
    r"\s*(?:(?:rm|dd|mkfs(?:\.[a-z0-9]+)?)\b|>>)",
    re.IGNORECASE,
)


class ShellInjectionInspector:
    """Inspector that flags shell-injection-shaped patterns in inspected text."""

    name: str = "ShellInjectionInspector"

    def __init__(
        self,
        *,
        capture_raw_matches: bool = False,
        max_input_chars: int = 65_536,
        phases: Iterable[str] = _DEFAULT_PHASES,
        logger: Logger | None = None,
    ) -> None:
        if max_input_chars <= 0:
            raise ConfigSchemaError(
                "ShellInjectionInspector: max_input_chars must be > 0",
                code="config.type_mismatch",
                details={"field": "max_input_chars"},
            )
        self._capture_raw_matches = bool(capture_raw_matches)
        self._max_input_chars = int(max_input_chars)
        self._phases = frozenset(phases)
        self._logger: Logger = logger or NullLogger()
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
            # Sanity-check tokenization: posix=True so the lexer enforces
            # quote balancing. If shlex can not tokenize the text, treat
            # it as unparseable per the documented failure mode.
            list(shlex.shlex(text, posix=True))
        except ValueError:
            self._emit_unparseable("malformed_quoting", len(text))
            return result

        new_findings: list[Finding] = list(result.findings)
        new_findings.extend(self._scan(text))

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
    # Quote-aware scanner
    # ------------------------------------------------------------------

    def _scan(self, text: str) -> list[Finding]:
        # `;` alone is too ambiguous to flag in arbitrary prose ("first, X;
        # then Y."), so command-chaining via `;` is only emitted when the
        # input ALSO carries an unambiguous shell sigil (substitution,
        # destructive pipe, or one of the harder operators `&&` / `||`).
        findings: list[Finding] = []
        semicolon_findings: list[Finding] = []
        has_unambiguous_shell_marker = False
        n = len(text)
        i = 0
        in_single = False
        in_double = False
        while i < n:
            ch = text[i]
            # Backslash escapes the next character outside single quotes.
            if ch == "\\" and not in_single and i + 1 < n:
                i += 2
                continue
            if ch == "'" and not in_double:
                in_single = not in_single
                i += 1
                continue
            if ch == '"' and not in_single:
                in_double = not in_double
                i += 1
                continue

            if in_single:
                # Inside single quotes nothing is special; skip.
                i += 1
                continue

            # Command substitution `$(...)` — both unquoted and inside
            # double quotes execute substitution in POSIX shell.
            if ch == "$" and i + 1 < n and text[i + 1] == "(":
                end = _matching_close(text, i + 1)
                if end is None:
                    end = n
                else:
                    end += 1
                findings.append(self._make_finding("shell.command_substitution", text, i, end))
                has_unambiguous_shell_marker = True
                i = end
                continue

            # Backtick substitution.
            if ch == "`":
                close = text.find("`", i + 1)
                end = close + 1 if close != -1 else n
                findings.append(self._make_finding("shell.command_substitution", text, i, end))
                has_unambiguous_shell_marker = True
                i = end
                continue

            if in_double:
                # The remaining metacharacters do not chain commands
                # while inside double quotes.
                i += 1
                continue

            # Pipe into destructive command: `|` not followed by `|`.
            if ch == "|" and (i + 1 >= n or text[i + 1] != "|"):
                tail = text[i + 1 :]
                m = _DESTRUCTIVE_PIPE_RE.match(tail)
                if m is not None:
                    end = i + 1 + m.end()
                    findings.append(self._make_finding("shell.pipe_into_destructive", text, i, end))
                    has_unambiguous_shell_marker = True
                    i = end
                    continue
                # Plain pipe (non-destructive) — ignored to avoid noise
                # on benign LLM-generated piped commands like `ls | wc`.
                i += 1
                continue

            # Command chaining: `&&` and `||` are unambiguously shell;
            # `;` is held aside until the rest of the scan tells us
            # whether we are in a shell-shaped or prose-shaped input.
            if ch == ";":
                semicolon_findings.append(
                    self._make_finding("shell.command_chaining", text, i, i + 1)
                )
                i += 1
                continue
            if ch == "&" and i + 1 < n and text[i + 1] == "&":
                findings.append(self._make_finding("shell.command_chaining", text, i, i + 2))
                has_unambiguous_shell_marker = True
                i += 2
                continue
            if ch == "|" and i + 1 < n and text[i + 1] == "|":
                findings.append(self._make_finding("shell.command_chaining", text, i, i + 2))
                has_unambiguous_shell_marker = True
                i += 2
                continue

            i += 1
        if has_unambiguous_shell_marker or _looks_like_shell_command(text):
            findings.extend(semicolon_findings)
        return findings

    def _make_finding(self, subtype: str, text: str, start: int, end: int) -> Finding:
        raw = text[start:end]
        return build_code_injection_finding(
            inspector_name=self.name,
            subtype=subtype,
            span=(start, end),
            raw_text=raw,
            capture_raw_matches=self._capture_raw_matches,
        )

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


_SHELL_CHAIN_PROBE_RE = re.compile(
    r"(?<![\w/])"
    r"(?P<lhs>(?:[\w./-]+(?:\s+(?:-{1,2}[\w-]+|[\w./-]+))*))"
    r"\s*;\s*"
    r"(?P<rhs>(?:[\w./-]+(?:\s+(?:-{1,2}[\w-]+|[\w./-]+))*))"
)

_PROSE_TOKEN_AFTER_SEMI_RE = re.compile(r";\s*[A-Za-z]+\s+[A-Za-z]+\s+[A-Za-z]+")


def _looks_like_shell_command(text: str) -> bool:
    """Return True when `;` chaining occurs between command-shaped tokens.

    A "command-shaped" side is a short alphanumeric token (with optional
    `-`, `.`, `/`) followed by zero or more option-like or path-like
    arguments. Long English-prose continuations after `;` (three or more
    word tokens in a row) are taken as evidence that the `;` is
    sentence-style rather than shell-chaining.
    """
    if _PROSE_TOKEN_AFTER_SEMI_RE.search(text):
        return False
    return _SHELL_CHAIN_PROBE_RE.search(text) is not None


def _matching_close(text: str, open_paren: int) -> int | None:
    depth = 0
    i = open_paren
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


__all__ = ["ShellInjectionInspector"]
