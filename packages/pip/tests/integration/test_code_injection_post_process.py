"""Integration test for code-injection inspectors on the post-process phase.

Drives each inspector directly with a post-process GuardResult and
asserts the resulting findings carry the expected subtype + fingerprint
metadata, that the documented RefusalCode entries exist for the new
inspector classes, and that the registered refusal templates are
resolvable so an operator wiring a PolicyRule with these codes builds a
non-empty refusal envelope.
"""

from __future__ import annotations

import pytest
from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.refusal.templates import get_refusal_template
from arc_guard_core.types import GuardResult

from arc_guard.inspectors.code_injection import (
    ShellInjectionInspector,
    SqlInjectionInspector,
    TemplateInjectionInspector,
)


def _post(text: str) -> GuardResult:
    return GuardResult(text=text, action="pass", findings=(), phase="post_process")


@pytest.mark.asyncio
@pytest.mark.requires_code_injection
async def test_sql_inspector_post_process_blocking_payload() -> None:
    inspector = SqlInjectionInspector()
    out = await inspector.inspect(
        _post("SELECT * FROM users WHERE id = 1; DROP TABLE users; --")
    )
    assert out.findings, "SQL inspector must emit at least one finding"
    sql_subtypes = {f.entity_type for f in out.findings}
    assert sql_subtypes & {
        "sql.stacked_statement",
        "sql.comment_terminator",
        "sql.union_injection",
    }
    for finding in out.findings:
        assert finding.inspector == "SqlInjectionInspector"
        assert "fingerprint" in finding.metadata
        assert finding.metadata["fingerprint"]["hash"].startswith("sha256:")

    # The matching refusal code is registered with a non-empty template.
    template = get_refusal_template(RefusalCode.SQL_INJECTION)
    assert template.human_message
    assert template.next_steps


@pytest.mark.asyncio
async def test_shell_inspector_post_process_blocking_payload() -> None:
    inspector = ShellInjectionInspector()
    out = await inspector.inspect(
        _post("ls /tmp; cat /etc/passwd | rm -rf /tmp")
    )
    assert out.findings
    shell_subtypes = {f.entity_type for f in out.findings}
    assert shell_subtypes & {
        "shell.command_substitution",
        "shell.pipe_into_destructive",
        "shell.command_chaining",
    }
    for finding in out.findings:
        assert finding.inspector == "ShellInjectionInspector"
        assert "fingerprint" in finding.metadata

    template = get_refusal_template(RefusalCode.SHELL_INJECTION)
    assert template.human_message
    assert template.next_steps


@pytest.mark.asyncio
async def test_template_inspector_post_process_blocking_payload() -> None:
    inspector = TemplateInjectionInspector()
    out = await inspector.inspect(
        _post("{{ config.__class__.__init__.__globals__ }} <script>x()</script>")
    )
    assert out.findings
    tmpl_subtypes = {f.entity_type for f in out.findings}
    assert tmpl_subtypes & {"template.sandbox_escape", "template.active_html"}
    for finding in out.findings:
        assert finding.inspector == "TemplateInjectionInspector"
        assert "fingerprint" in finding.metadata

    template = get_refusal_template(RefusalCode.TEMPLATE_INJECTION)
    assert template.human_message
    assert template.next_steps
