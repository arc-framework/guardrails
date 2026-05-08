"""Shared helpers for the code-injection inspectors.

Two pieces of plumbing:

- ``build_code_injection_finding`` — uniform ``Finding`` construction so
  every finding produced by SQL / shell / template inspectors carries the
  same metadata shape (fingerprint, subtype, inspector, optional raw_match).
- ``closed_posture_inspect`` — decorator that wraps an inspector's
  ``inspect`` coroutine. An *unhandled* exception is logged and re-raised
  as ``StrategyError`` so the pipeline's existing closed-posture
  conversion produces a refusal envelope. The decorator is NOT used to
  swallow expected unparseable-input cases — those return no finding and
  emit a structured event from inside the inspector.
"""

from __future__ import annotations

import functools
import logging
import secrets
from collections.abc import Awaitable, Callable
from typing import Any

from arc_guard_core.exceptions import ArcGuardError, StrategyError
from arc_guard_core.types import Finding, GuardResult, RiskLevel

from arc_guard.inspectors.code_injection._fingerprint import compute_fingerprint


def build_code_injection_finding(
    *,
    inspector_name: str,
    subtype: str,
    span: tuple[int, int],
    raw_text: str,
    capture_raw_matches: bool,
    score: float = 1.0,
    risk_level: RiskLevel = RiskLevel.HIGH,
) -> Finding:
    """Construct a ``Finding`` with the documented code-injection metadata.

    The metadata always carries ``fingerprint``, ``subtype``, and
    ``inspector``. The literal matched text is added under ``raw_match``
    only when ``capture_raw_matches`` is True; otherwise the key is
    omitted entirely so default lifecycle events never carry the working
    attack payload.
    """
    start, end = span
    metadata: dict[str, Any] = {
        "fingerprint": compute_fingerprint(raw_text),
        "subtype": subtype,
        "inspector": inspector_name,
    }
    if capture_raw_matches:
        metadata["raw_match"] = raw_text
    return Finding(
        entity_type=subtype,
        start=start,
        end=end,
        risk_level=risk_level,
        inspector=inspector_name,
        score=score,
        metadata=metadata,
    )


_AsyncInspect = Callable[[Any, GuardResult], Awaitable[GuardResult]]


def closed_posture_inspect(
    func: _AsyncInspect,
) -> _AsyncInspect:
    """Wrap an inspector's ``inspect`` coroutine with closed-posture handling.

    Any unhandled exception escaping the wrapped coroutine is logged with
    a generated traceback id, then re-raised as ``StrategyError`` so the
    pipeline's existing failure-mode machinery converts it into a refusal
    envelope. Expected unparseable-input handling stays inside the
    inspector and must not raise.
    """

    @functools.wraps(func)
    async def wrapper(self: Any, result: GuardResult) -> GuardResult:
        try:
            return await func(self, result)
        except ArcGuardError:
            # ArcGuard-typed exceptions (StrategyError, ConfigSchemaError, ...)
            # already carry the failure-mode metadata the pipeline expects;
            # let them propagate without re-wrapping.
            raise
        except Exception as exc:
            inspector_name = type(self).__name__
            traceback_id = secrets.token_hex(8)
            logging.getLogger(__name__).warning(
                "guard.code_injection.inspector_failed",
                extra={
                    "inspector": inspector_name,
                    "traceback_id": traceback_id,
                    "exception_type": type(exc).__name__,
                },
            )
            raise StrategyError(
                f"{inspector_name} failed during inspection",
                code="strategy.failed",
                details={
                    "inspector": inspector_name,
                    "exception_type": type(exc).__name__,
                    "traceback_id": traceback_id,
                },
                cause=exc,
            ) from exc

    return wrapper


__all__ = [
    "build_code_injection_finding",
    "closed_posture_inspect",
]
