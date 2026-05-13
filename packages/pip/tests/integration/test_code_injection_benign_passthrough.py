"""Benign-passthrough behavior with all three code-injection inspectors enabled.

Plain prose without executable artifacts must produce no findings and pass
through unchanged when SqlInjectionInspector + ShellInjectionInspector +
TemplateInjectionInspector are all wired into the pipeline.
"""

from __future__ import annotations

import pytest
from arc_guard_core.types import GuardContext, GuardInput

from arc_guard.config_env import GuardConfig
from arc_guard.inspectors.code_injection import (
    ShellInjectionInspector,
    SqlInjectionInspector,
    TemplateInjectionInspector,
)
from arc_guard.pipeline import GuardPipeline

_BENIGN_RESPONSES = (
    "Sure, here are the steps: first, open your editor; then save the file.",
    "Hello! How can I help you today?",
    "The recipe calls for 2 cups of flour and 1 cup of sugar.",
    "Common SQL keywords include SELECT, FROM, WHERE.",
    "Jinja templates use {{ name }} placeholders for variables.",
)


def _pipeline_with_all_three_inspectors() -> GuardPipeline:
    return GuardPipeline(
        config=GuardConfig(),
        inspectors=[
            SqlInjectionInspector(),
            ShellInjectionInspector(),
            TemplateInjectionInspector(),
        ],
    )


@pytest.mark.asyncio
@pytest.mark.requires_code_injection
async def test_benign_responses_pass_through_unchanged() -> None:
    pipeline = _pipeline_with_all_three_inspectors()
    for payload in _BENIGN_RESPONSES:
        result = await pipeline.post_process(
            GuardInput(text=payload, context=GuardContext(source="output"))
        )
        code_injection_findings = [
            f for f in result.findings if f.entity_type.startswith(("sql.", "shell.", "template."))
        ]
        assert code_injection_findings == [], (
            f"benign payload triggered findings: {payload!r} -> {code_injection_findings}"
        )
        assert result.refusal is None
        assert result.action == "pass"
        assert result.text == payload
