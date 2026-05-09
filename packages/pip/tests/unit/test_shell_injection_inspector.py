"""Unit tests for ShellInjectionInspector."""

from __future__ import annotations

from typing import Any

import pytest
from arc_guard_core.types import GuardResult

from arc_guard.inspectors.code_injection.shell import ShellInjectionInspector


class _RecordingLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def bind(self, **fields: Any) -> _RecordingLogger:
        return self

    def event(self, name: str, *, level: str = "info", **fields: Any) -> None:
        self.events.append((name, {"level": level, **fields}))


def _post_result(text: str) -> GuardResult:
    return GuardResult(text=text, action="pass", findings=(), phase="post_process")


async def _inspect(inspector: ShellInjectionInspector, text: str) -> GuardResult:
    return await inspector.inspect(_post_result(text))


@pytest.mark.asyncio
async def test_detects_dollar_paren_command_substitution() -> None:
    inspector = ShellInjectionInspector()
    out = await _inspect(inspector, "echo $(rm -rf /tmp/secrets)")
    subtypes = {f.entity_type for f in out.findings}
    assert "shell.command_substitution" in subtypes


@pytest.mark.asyncio
async def test_detects_backtick_command_substitution() -> None:
    inspector = ShellInjectionInspector()
    out = await _inspect(inspector, "echo `whoami`")
    subtypes = {f.entity_type for f in out.findings}
    assert "shell.command_substitution" in subtypes


@pytest.mark.asyncio
async def test_detects_pipe_into_destructive_rm() -> None:
    inspector = ShellInjectionInspector()
    out = await _inspect(inspector, "ls /tmp | rm -rf /tmp/foo")
    subtypes = {f.entity_type for f in out.findings}
    assert "shell.pipe_into_destructive" in subtypes


@pytest.mark.asyncio
async def test_detects_pipe_into_dd() -> None:
    inspector = ShellInjectionInspector()
    out = await _inspect(inspector, "cat /etc/passwd | dd of=/dev/sda")
    subtypes = {f.entity_type for f in out.findings}
    assert "shell.pipe_into_destructive" in subtypes


@pytest.mark.asyncio
async def test_detects_pipe_into_append_redirect() -> None:
    inspector = ShellInjectionInspector()
    out = await _inspect(inspector, "echo hi | >> /etc/passwd")
    subtypes = {f.entity_type for f in out.findings}
    assert "shell.pipe_into_destructive" in subtypes


@pytest.mark.asyncio
async def test_detects_command_chaining_semicolon() -> None:
    inspector = ShellInjectionInspector()
    out = await _inspect(inspector, "ls /tmp; cat /etc/passwd")
    subtypes = {f.entity_type for f in out.findings}
    assert "shell.command_chaining" in subtypes


@pytest.mark.asyncio
async def test_detects_command_chaining_double_amp() -> None:
    inspector = ShellInjectionInspector()
    out = await _inspect(inspector, "make && cat /etc/passwd")
    subtypes = {f.entity_type for f in out.findings}
    assert "shell.command_chaining" in subtypes


@pytest.mark.asyncio
async def test_detects_command_chaining_double_pipe() -> None:
    inspector = ShellInjectionInspector()
    out = await _inspect(inspector, "make || cat /etc/passwd")
    subtypes = {f.entity_type for f in out.findings}
    assert "shell.command_chaining" in subtypes


@pytest.mark.asyncio
async def test_single_quoted_meta_chars_do_not_trigger() -> None:
    inspector = ShellInjectionInspector()
    out = await _inspect(
        inspector,
        "how do I write '$(date) and ; and && safely' in bash documentation?",
    )
    assert out.findings == ()


@pytest.mark.asyncio
async def test_escaped_dollar_paren_does_not_trigger() -> None:
    inspector = ShellInjectionInspector()
    out = await _inspect(inspector, r"how do I write \$(date) in bash")
    assert out.findings == ()


@pytest.mark.asyncio
async def test_benign_shell_keyword_prose_passes() -> None:
    inspector = ShellInjectionInspector()
    out = await _inspect(
        inspector,
        "Use the rm command to remove files and dd to copy disks.",
    )
    assert out.findings == ()


@pytest.mark.asyncio
async def test_oversize_input_emits_observability_event_and_no_finding() -> None:
    logger = _RecordingLogger()
    inspector = ShellInjectionInspector(max_input_chars=32, logger=logger)
    out = await _inspect(
        inspector,
        "echo $(rm -rf /tmp); cat /etc/passwd; echo more text" + ("x" * 100),
    )
    assert out.findings == ()
    names = [name for name, _ in logger.events]
    assert "guard.code_injection.unparseable_input" in names


@pytest.mark.asyncio
async def test_pre_process_phase_skipped_by_default() -> None:
    inspector = ShellInjectionInspector()
    pre = GuardResult(
        text="echo $(rm -rf /tmp); cat /etc/passwd",
        phase="pre_process",
    )
    out = await inspector.inspect(pre)
    assert out.findings == ()


@pytest.mark.asyncio
async def test_capture_raw_matches_default_off() -> None:
    inspector = ShellInjectionInspector()
    out = await _inspect(inspector, "ls; rm -rf /")
    for finding in out.findings:
        assert "raw_match" not in finding.metadata
        assert "fingerprint" in finding.metadata


@pytest.mark.asyncio
async def test_capture_raw_matches_true_includes_raw_match() -> None:
    inspector = ShellInjectionInspector(capture_raw_matches=True)
    out = await _inspect(inspector, "ls; rm -rf /")
    assert any("raw_match" in f.metadata for f in out.findings)
