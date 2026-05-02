"""Default ``AttributeRedactor`` implementation: ``BoundedRedactor``.

Sanitizes or rejects attribute values before they reach a backend.
Three rejection paths:

- key not in the metric attribute allow-list (only checked on the
  metric path; span attributes pass without an allow-list check),
- value's repr exceeds the configured byte cap,
- value's string-coerced form contains a chunk of the run's input
  text (a runtime check that pairs with the CI-time leak scanner).

Each rejection carries a stable ``reason`` string suitable for the
``arc_guardrails.observability.attribute_dropped`` metric label.

Concurrency: thread-safe (the redactor itself is stateless except for
the optional run-context handle, which is set per-run by the stage
runner).
Failure mode: never raises; returns ``RedactionResult(accepted=False,
reason=...)`` instead.
"""

from __future__ import annotations

from typing import Any, Final

from arc_guard_core.observability_config import ObservabilityConfig
from arc_guard_core.protocols.attribute_redactor import RedactionResult

# Stable rejection reasons. Used as metric labels — keep cardinality low.
REASON_NOT_IN_ALLOW_LIST: Final[str] = "not_in_allow_list"
REASON_EXCEEDS_BYTE_CAP: Final[str] = "exceeds_byte_cap"
REASON_CONTAINS_INPUT_SUBSTRING: Final[str] = "contains_input_substring"

# Minimum substring length to flag. Single-character matches would
# trigger on every input that mentions any letter; even short matches
# like "is" or "the" are too generic. The threshold catches real PII
# (emails, phone-shaped strings, internal names) without flagging common
# stop-words.
_MIN_SUBSTRING_LENGTH: Final[int] = 4


class BoundedRedactor:
    """Sanitize-or-reject attribute values before they reach a backend.

    The redactor is per-pipeline (created at pipeline construction). For
    each run it receives the originals via ``set_run_originals`` so the
    substring-rejection branch can scan against the actual input text.
    Distinguishes metric labels from span attributes via the ``is_metric``
    flag on ``sanitize_attribute``: only metric emissions enforce the
    allow-list (span attributes have their own per-stage allow-list
    documented in the contract).
    """

    def __init__(self, config: ObservabilityConfig | None = None) -> None:
        self._config = config or ObservabilityConfig()
        self._run_originals: tuple[str, ...] = ()

    def set_run_originals(self, originals: tuple[str, ...]) -> None:
        """Install the run-scoped originals against which substring search runs.

        The pipeline calls this at run entry with the input text and any
        finding-matched substrings; the stage runner calls
        ``clear_run_originals`` at run exit.
        """
        self._run_originals = originals

    def clear_run_originals(self) -> None:
        self._run_originals = ()

    # ``AttributeRedactor`` Protocol method — used for span attributes
    # and log fields (no allow-list enforcement).
    def sanitize(self, key: str, value: Any) -> RedactionResult:
        return self._sanitize_common(key, value, is_metric=False)

    # Metric-emission path enforces the allow-list in addition to the
    # byte cap and substring search.
    def sanitize_metric_label(self, key: str, value: Any) -> RedactionResult:
        return self._sanitize_common(key, value, is_metric=True)

    def _sanitize_common(self, key: str, value: Any, *, is_metric: bool) -> RedactionResult:
        if is_metric and key not in self._config.metric_attribute_allow_list:
            return RedactionResult(accepted=False, reason=REASON_NOT_IN_ALLOW_LIST)

        # Byte-cap enforcement on the repr to catch accidental dumps of
        # large structured values (lists, dicts, etc.).
        encoded = repr(value).encode("utf-8")
        if len(encoded) > self._config.max_attribute_bytes:
            return RedactionResult(accepted=False, reason=REASON_EXCEEDS_BYTE_CAP)

        # Substring rejection: scan the string-coerced value against the
        # run originals. Only meaningful for string-coercible values; ints
        # and other primitives can't carry user-derived text.
        if self._run_originals:
            text = str(value)
            for original in self._run_originals:
                if not original or len(original) < _MIN_SUBSTRING_LENGTH:
                    continue
                # Either the attribute contains a chunk of the original,
                # or the original is contained in the attribute.
                if (
                    self._has_overlap(text, original)
                    or self._has_overlap(original, text)
                ):
                    return RedactionResult(
                        accepted=False, reason=REASON_CONTAINS_INPUT_SUBSTRING,
                    )

        return RedactionResult(accepted=True, value=value)

    @staticmethod
    def _has_overlap(haystack: str, needle: str) -> bool:
        """True when ``haystack`` contains a chunk of ``needle`` of at least
        ``_MIN_SUBSTRING_LENGTH`` characters.
        """
        if len(needle) < _MIN_SUBSTRING_LENGTH:
            return False
        # Whole-needle match is the common case — check it cheaply first.
        if needle in haystack:
            return True
        # Otherwise scan for any contiguous chunk of length >= threshold.
        for start in range(len(needle) - _MIN_SUBSTRING_LENGTH + 1):
            chunk = needle[start : start + _MIN_SUBSTRING_LENGTH]
            if chunk in haystack:
                return True
        return False


__all__ = [
    "BoundedRedactor",
    "REASON_NOT_IN_ALLOW_LIST",
    "REASON_EXCEEDS_BYTE_CAP",
    "REASON_CONTAINS_INPUT_SUBSTRING",
]
