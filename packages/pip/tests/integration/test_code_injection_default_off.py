"""Default-off behavior for the code-injection inspectors.

Constructing a GuardPipeline without any code-injection inspector must
behave identically to the existing pipeline on the same content: no
findings from the new inspectors, no implicit activation, no surprise
refusal.
"""

from __future__ import annotations

import pytest
from arc_guard_core.types import GuardContext, GuardInput

from arc_guard.config_env import GuardConfig
from arc_guard.pipeline import GuardPipeline

_ATTACK_PAYLOADS = (
    "SELECT * FROM users WHERE id=1; DROP TABLE users; --",
    "echo $(rm -rf /) ; cat /etc/passwd",
    "{{ config.__class__.__init__.__globals__ }} <script>alert(1)</script>",
)


def _bare_pipeline() -> GuardPipeline:
    # Empty inspector list means no code-injection inspectors are active;
    # the pipeline falls back to its default flag-driven chain (no PII /
    # injection inspectors are wired here either, so the pipeline runs
    # cleanly on the inputs below).
    return GuardPipeline(config=GuardConfig(), inspectors=[])


@pytest.mark.asyncio
async def test_no_code_injection_findings_when_inspectors_absent() -> None:
    pipeline = _bare_pipeline()
    for payload in _ATTACK_PAYLOADS:
        result = await pipeline.post_process(
            GuardInput(text=payload, context=GuardContext(source="output"))
        )
        code_injection_findings = [
            f
            for f in result.findings
            if f.entity_type.startswith(("sql.", "shell.", "template."))
        ]
        assert code_injection_findings == []
        assert result.refusal is None
        assert result.action == "pass"


@pytest.mark.asyncio
async def test_pre_process_phase_no_implicit_activation() -> None:
    pipeline = _bare_pipeline()
    for payload in _ATTACK_PAYLOADS:
        result = await pipeline.pre_process(
            GuardInput(text=payload, context=GuardContext(source="input"))
        )
        code_injection_findings = [
            f
            for f in result.findings
            if f.entity_type.startswith(("sql.", "shell.", "template."))
        ]
        assert code_injection_findings == []
        assert result.refusal is None
