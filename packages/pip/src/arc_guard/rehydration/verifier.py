"""``NullRehydrationVerifier`` — structural-only checks.

Implements the two checks every verifier must run:

- **Check 1 — Placeholder provenance**: every placeholder in the
  rehydration candidate must also appear in the sanitized prompt.
  Invented placeholders fail the check.
- **Check 2 — Structural shift**: for each placeholder occurrence in
  the candidate, a 16-char window before+after must overlap with at
  least one occurrence in the sanitized prompt. A placeholder that
  moved to a different syntactic context (e.g. inside backticks for
  literal-example position) fails the check.

Skips Check 3 (safety regression) — that lands in the canned semantic
verifier from the ``[semantic]`` extra. The null verifier is the
offline-capable default; it is the structural floor that always runs.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from arc_guard_core.protocols.rehydration_verifier import RehydrationVerdict

_PLACEHOLDER_PATTERN: re.Pattern[str] = re.compile(r"\[[A-Z][A-Z0-9_]*(?:_\d+)?\]")
_WINDOW_CHARS = 16


def _extract_placeholders(text: str) -> list[tuple[str, int, int]]:
    """Return ``[(placeholder_name, start, end), ...]`` for every match."""
    return [
        (match.group(0), match.start(), match.end())
        for match in _PLACEHOLDER_PATTERN.finditer(text)
    ]


def _window(text: str, start: int, end: int) -> tuple[str, str]:
    """Return the (before, after) ``_WINDOW_CHARS`` slices around a span."""
    before_start = max(0, start - _WINDOW_CHARS)
    after_end = min(len(text), end + _WINDOW_CHARS)
    return text[before_start:start], text[end:after_end]


class NullRehydrationVerifier:
    """Default offline-capable verifier: placeholder provenance + structural shift."""

    def verify(
        self,
        *,
        sanitized_prompt: str,
        rehydration_candidate: str,
        entity_map: Mapping[str, str],
    ) -> RehydrationVerdict:
        # Empty entity map → nothing to rehydrate.
        if not entity_map:
            return RehydrationVerdict(
                decision="accept",
                reason="all_checks_passed",
            )

        prompt_placeholders = _extract_placeholders(sanitized_prompt)
        prompt_names: set[str] = {name for name, _, _ in prompt_placeholders}
        candidate_placeholders = _extract_placeholders(rehydration_candidate)

        per_placeholder: dict[str, bool] = {}
        first_failed_reason: str | None = None

        for name, c_start, c_end in candidate_placeholders:
            # Check 1: provenance.
            if name not in prompt_names:
                per_placeholder[name] = False
                if first_failed_reason is None:
                    first_failed_reason = "invented_placeholder"
                continue
            # Check 2: structural shift.
            cand_before, cand_after = _window(rehydration_candidate, c_start, c_end)
            cand_before_cls = _adjacent_class(cand_before, side="before")
            cand_after_cls = _adjacent_class(cand_after, side="after")
            structurally_aligned = False
            for prompt_name, p_start, p_end in prompt_placeholders:
                if prompt_name != name:
                    continue
                p_before, p_after = _window(sanitized_prompt, p_start, p_end)
                if (
                    _adjacent_class(p_before, side="before") == cand_before_cls
                    and _adjacent_class(p_after, side="after") == cand_after_cls
                ):
                    structurally_aligned = True
                    break
            per_placeholder[name] = structurally_aligned
            if not structurally_aligned and first_failed_reason is None:
                first_failed_reason = "structural_shift"

        if not per_placeholder:
            return RehydrationVerdict(
                decision="accept",
                reason="all_checks_passed",
            )

        all_pass = all(per_placeholder.values())
        all_fail = not any(per_placeholder.values())

        if all_pass:
            return RehydrationVerdict(
                decision="accept",
                reason="all_checks_passed",
            )
        if all_fail:
            assert first_failed_reason is not None
            return RehydrationVerdict(
                decision="reject",
                reason=first_failed_reason,
            )
        return RehydrationVerdict(
            decision="partial",
            reason="partial_verdict",
            per_placeholder=per_placeholder,
        )


_STRUCTURAL_DELIMITERS: frozenset[str] = frozenset({
    "`", "'", '"', "(", ")", "[", "]", "{", "}", "<", ">",
})


def _adjacent_class(window: str, *, side: str) -> str:
    """Classify the immediately-adjacent character into a syntactic class.

    ``side="before"`` looks at the LAST char of the before-window;
    ``side="after"`` looks at the FIRST char of the after-window. The
    class is one of:

    - ``""`` — empty window (placeholder at start/end of text)
    - ``" "`` — whitespace (any \\s) — the common value-position case
    - the literal delimiter character — code fences, quotes, brackets
    - ``"a"`` — alphanumeric (in-word position, also a structural shift
      from a typical free-text value position)
    - ``","``, ``":"``, ``";"``, ``"."`` — common punctuation

    Two placeholders are in the same structural context when their
    before-class AND after-class match.
    """
    if not window:
        return ""
    char = window[-1] if side == "before" else window[0]
    if char in _STRUCTURAL_DELIMITERS:
        return char
    if char.isspace():
        return " "
    if char.isalnum():
        return "a"
    return char  # punctuation, etc. — keep literal


__all__ = ["NullRehydrationVerifier"]
