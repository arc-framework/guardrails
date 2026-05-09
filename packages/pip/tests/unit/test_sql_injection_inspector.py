"""Unit tests for SqlInjectionInspector.

Covers the documented detection subtypes (stacked statement, comment
terminator, union injection), benign-passthrough on documentation
snippets, the oversize-input observability event, and the missing-extra
ConfigurationError path.
"""

from __future__ import annotations

import sys
from typing import Any

import pytest
from arc_guard_core.exceptions import ConfigSchemaError
from arc_guard_core.types import GuardResult

from arc_guard.inspectors.code_injection.sql import SqlInjectionInspector

pytestmark = pytest.mark.requires_code_injection


class _RecordingLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def bind(self, **fields: Any) -> _RecordingLogger:
        return self

    def event(self, name: str, *, level: str = "info", **fields: Any) -> None:
        self.events.append((name, {"level": level, **fields}))


def _post_result(text: str) -> GuardResult:
    return GuardResult(text=text, action="pass", findings=(), phase="post_process")


async def _inspect(inspector: SqlInjectionInspector, text: str) -> GuardResult:
    return await inspector.inspect(_post_result(text))


@pytest.mark.asyncio
async def test_detects_stacked_statement() -> None:
    inspector = SqlInjectionInspector()
    text = "SELECT id FROM users; DROP TABLE users;"
    out = await _inspect(inspector, text)
    subtypes = {f.entity_type for f in out.findings}
    assert "sql.stacked_statement" in subtypes


@pytest.mark.asyncio
async def test_detects_classic_quote_break_attack() -> None:
    inspector = SqlInjectionInspector()
    text = "SELECT * FROM users WHERE name = 'admin'; DROP TABLE users; --"
    out = await _inspect(inspector, text)
    subtypes = {f.entity_type for f in out.findings}
    assert "sql.stacked_statement" in subtypes


@pytest.mark.asyncio
async def test_detects_comment_terminator() -> None:
    inspector = SqlInjectionInspector()
    text = "SELECT * FROM users WHERE id = 1 -- AND password = 'x'"
    out = await _inspect(inspector, text)
    subtypes = {f.entity_type for f in out.findings}
    assert "sql.comment_terminator" in subtypes


@pytest.mark.asyncio
async def test_detects_block_comment_terminator() -> None:
    inspector = SqlInjectionInspector()
    text = "SELECT * FROM users WHERE id = 1 /* hidden */ AND owner = 'a'"
    out = await _inspect(inspector, text)
    subtypes = {f.entity_type for f in out.findings}
    assert "sql.comment_terminator" in subtypes


@pytest.mark.asyncio
async def test_detects_union_injection() -> None:
    inspector = SqlInjectionInspector()
    text = (
        "SELECT id FROM users WHERE id = 1 "
        "UNION SELECT username, password FROM admins"
    )
    out = await _inspect(inspector, text)
    subtypes = {f.entity_type for f in out.findings}
    assert "sql.union_injection" in subtypes


@pytest.mark.asyncio
async def test_benign_documentation_snippet_passes() -> None:
    inspector = SqlInjectionInspector()
    text = "SELECT * FROM users"
    out = await _inspect(inspector, text)
    assert out.findings == ()


@pytest.mark.asyncio
async def test_prose_with_semicolon_does_not_false_positive() -> None:
    inspector = SqlInjectionInspector()
    text = (
        "In SQL you can use SELECT * FROM users to get all rows; "
        "this is taught in databases."
    )
    out = await _inspect(inspector, text)
    # The trailing prose is not a SQL statement; stacked-statement detection
    # must require both sides to look like SQL.
    subtypes = {f.entity_type for f in out.findings}
    assert "sql.stacked_statement" not in subtypes


@pytest.mark.asyncio
async def test_oversize_input_emits_observability_event_and_no_finding() -> None:
    logger = _RecordingLogger()
    inspector = SqlInjectionInspector(max_input_chars=64, logger=logger)
    text = "SELECT id FROM users; DROP TABLE users;" + ("x" * 200)
    out = await _inspect(inspector, text)
    assert out.findings == ()
    names = [name for name, _ in logger.events]
    assert "guard.code_injection.unparseable_input" in names
    payload = next(p for n, p in logger.events if n == "guard.code_injection.unparseable_input")
    assert payload["reason"] == "size_limit"
    assert payload["inspector"] == "SqlInjectionInspector"


@pytest.mark.asyncio
async def test_pre_process_phase_skipped_by_default() -> None:
    inspector = SqlInjectionInspector()
    pre = GuardResult(text="DROP TABLE users; SELECT 1;", phase="pre_process")
    out = await inspector.inspect(pre)
    # Default phases is post_process only.
    assert out.findings == ()


@pytest.mark.asyncio
async def test_capture_raw_matches_default_off_omits_raw_match() -> None:
    inspector = SqlInjectionInspector()
    text = "SELECT 1; DROP TABLE users;"
    out = await _inspect(inspector, text)
    for finding in out.findings:
        assert "raw_match" not in finding.metadata
        assert "fingerprint" in finding.metadata


@pytest.mark.asyncio
async def test_capture_raw_matches_true_includes_raw_match() -> None:
    inspector = SqlInjectionInspector(capture_raw_matches=True)
    text = "SELECT 1; DROP TABLE users;"
    out = await _inspect(inspector, text)
    assert any("raw_match" in f.metadata for f in out.findings)


@pytest.mark.asyncio
async def test_missing_extra_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inspector = SqlInjectionInspector()
    # Simulate the extra not being installed by hiding sqlparse from the import.
    monkeypatch.setitem(sys.modules, "sqlparse", None)
    with pytest.raises(ConfigSchemaError) as excinfo:
        await _inspect(inspector, "SELECT 1")
    assert "code-injection" in str(excinfo.value)


def test_constructor_rejects_non_positive_max_chars() -> None:
    with pytest.raises(ConfigSchemaError):
        SqlInjectionInspector(max_input_chars=0)
