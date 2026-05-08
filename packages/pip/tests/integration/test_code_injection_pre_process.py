"""Pre-process phase opt-in for code-injection inspectors.

Verifies that operators with template-rendered prompts can scan user
input for template-injection sigils before forwarding to the LLM, by
constructing the inspector with phases={"pre_process"}.
"""

from __future__ import annotations

import pytest

from arc_guard_core.types import GuardResult

from arc_guard.inspectors.code_injection import TemplateInjectionInspector


@pytest.mark.asyncio
async def test_template_inspector_fires_on_pre_process_when_phase_opt_in() -> None:
    inspector = TemplateInjectionInspector(phases={"pre_process"})
    text = (
        "Please render: {{ config.__class__.__init__.__globals__['os'].popen('ls') }}"
    )
    pre_input = GuardResult(text=text, action="pass", findings=(), phase="pre_process")

    out = await inspector.inspect(pre_input)

    assert len(out.findings) >= 1
    subtypes = {f.entity_type for f in out.findings}
    assert any("template" in s for s in subtypes)


@pytest.mark.asyncio
async def test_template_inspector_does_not_fire_on_post_process_when_only_pre_phase_set() -> None:
    inspector = TemplateInjectionInspector(phases={"pre_process"})
    text = "Innocent post-process content {{ config.__class__ }}"
    post_input = GuardResult(text=text, action="pass", findings=(), phase="post_process")

    out = await inspector.inspect(post_input)

    assert out.findings == ()


@pytest.mark.asyncio
async def test_template_inspector_default_phases_is_post_process_only() -> None:
    """Default constructor (no phases= arg) = post-process only.

    A pre_process call against an input with template sigils must
    produce no finding when the inspector wasn't opted into pre_process.
    """
    inspector = TemplateInjectionInspector()
    text = "{{ config.__class__.__init__.__globals__['os'] }}"
    pre_input = GuardResult(text=text, action="pass", findings=(), phase="pre_process")

    out = await inspector.inspect(pre_input)

    assert out.findings == ()
