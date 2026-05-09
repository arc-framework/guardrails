"""Security soak: code-injection findings carry fingerprint-only by default.

The default `capture_raw_matches=False` configuration must guarantee that
no `Finding.metadata` dict contains a `raw_match` key, AND that the
serialized event payload (when emitted to a lifecycle sink) contains no
literal attack-payload string.

This is the load-bearing invariant for the threat model: the lifecycle
store / SIEM / dashboard must NEVER accumulate a working-attack catalog
under default settings.

When the operator explicitly opts in via `capture_raw_matches=True`, the
`raw_match` key IS present — verifying the opt-in works as documented.
"""

from __future__ import annotations

import json

import pytest
from arc_guard_core.types import GuardResult

from arc_guard.inspectors.code_injection import (
    ShellInjectionInspector,
    SqlInjectionInspector,
    TemplateInjectionInspector,
)

# Diverse attack corpus — each string is chosen so the inspectors fire.
SQL_ATTACKS = [
    "SELECT * FROM users; DROP TABLE users; --",
    "SELECT id FROM accounts WHERE name='admin' UNION SELECT password FROM users",
    "SELECT * FROM users; DELETE FROM users WHERE id > 0; --",
]

SHELL_ATTACKS = [
    "echo $(rm -rf /tmp/test)",
    "ls `whoami`",
    "cat file.txt | rm /etc/passwd",
    "echo hello && rm -rf /var/log",
]

TEMPLATE_ATTACKS = [
    "{{ config.__class__.__init__.__globals__['os'].popen('id') }}",
    "{{ ''.__class__.__mro__[1].__subclasses__() }}",
    "<script>alert(1)</script>",
    "<a href='javascript:fetch(`/api/keys`)'>click</a>",
    "<img onerror='steal()' src=x>",
]


def _inspect_sync(inspector, text):  # type: ignore[no-untyped-def]
    """Run an async inspect() in a sync test context."""
    import asyncio

    pre = GuardResult(text=text, action="pass", findings=(), phase="post_process")
    return asyncio.run(inspector.inspect(pre))


def _serialize(finding) -> str:  # type: ignore[no-untyped-def]
    """JSON-serialize a Finding for raw-string scanning."""
    md = dict(finding.metadata)
    # Recursively convert non-JSON-serializable values to strings
    return json.dumps(md, default=str)


@pytest.mark.parametrize("text", SQL_ATTACKS)
def test_sql_default_omits_raw_match(text: str) -> None:
    inspector = SqlInjectionInspector()
    out = _inspect_sync(inspector, text)
    findings = [f for f in out.findings if f.entity_type.startswith("sql.")]
    assert len(findings) >= 1
    for f in findings:
        assert "raw_match" not in f.metadata
        # The literal attack must not appear anywhere in the serialized event.
        assert text not in _serialize(f)


@pytest.mark.parametrize("text", SHELL_ATTACKS)
def test_shell_default_omits_raw_match(text: str) -> None:
    inspector = ShellInjectionInspector()
    out = _inspect_sync(inspector, text)
    findings = [f for f in out.findings if f.entity_type.startswith("shell.")]
    assert len(findings) >= 1
    for f in findings:
        assert "raw_match" not in f.metadata
        assert text not in _serialize(f)


@pytest.mark.parametrize("text", TEMPLATE_ATTACKS)
def test_template_default_omits_raw_match(text: str) -> None:
    inspector = TemplateInjectionInspector()
    out = _inspect_sync(inspector, text)
    findings = [f for f in out.findings if f.entity_type.startswith("template.")]
    assert len(findings) >= 1
    for f in findings:
        assert "raw_match" not in f.metadata
        assert text not in _serialize(f)


def test_sql_opt_in_includes_raw_match() -> None:
    inspector = SqlInjectionInspector(capture_raw_matches=True)
    out = _inspect_sync(inspector, SQL_ATTACKS[0])
    findings = [f for f in out.findings if f.entity_type.startswith("sql.")]
    assert len(findings) >= 1
    assert any("raw_match" in f.metadata for f in findings)


def test_shell_opt_in_includes_raw_match() -> None:
    inspector = ShellInjectionInspector(capture_raw_matches=True)
    out = _inspect_sync(inspector, SHELL_ATTACKS[0])
    findings = [f for f in out.findings if f.entity_type.startswith("shell.")]
    assert len(findings) >= 1
    assert any("raw_match" in f.metadata for f in findings)


def test_template_opt_in_includes_raw_match() -> None:
    inspector = TemplateInjectionInspector(capture_raw_matches=True)
    out = _inspect_sync(inspector, TEMPLATE_ATTACKS[0])
    findings = [f for f in out.findings if f.entity_type.startswith("template.")]
    assert len(findings) >= 1
    assert any("raw_match" in f.metadata for f in findings)


def test_fingerprint_metadata_always_present_at_default() -> None:
    """The fingerprint structure must replace the raw payload, not be absent."""
    inspector = SqlInjectionInspector()
    out = _inspect_sync(inspector, SQL_ATTACKS[0])
    findings = [f for f in out.findings if f.entity_type.startswith("sql.")]
    assert len(findings) >= 1
    fp = findings[0].metadata.get("fingerprint")
    assert isinstance(fp, dict)
    assert fp["hash"].startswith("sha256:")
    assert "length_chars" in fp
    assert "char_class" in fp
