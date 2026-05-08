"""Both-phase opt-in for a single code-injection inspector instance.

Verifies that an inspector with phases={"pre_process", "post_process"}
fires on either phase and produces independent findings when the same
content is inspected on both.
"""

from __future__ import annotations

import pytest

from arc_guard_core.types import GuardResult

from arc_guard.inspectors.code_injection import TemplateInjectionInspector


@pytest.mark.asyncio
async def test_inspector_with_both_phases_fires_on_pre_process() -> None:
    inspector = TemplateInjectionInspector(phases={"pre_process", "post_process"})
    text = "{{ config.__class__.__init__.__globals__ }}"
    pre_input = GuardResult(text=text, action="pass", findings=(), phase="pre_process")

    out = await inspector.inspect(pre_input)

    assert len(out.findings) >= 1


@pytest.mark.asyncio
async def test_inspector_with_both_phases_fires_on_post_process() -> None:
    inspector = TemplateInjectionInspector(phases={"pre_process", "post_process"})
    text = "{{ config.__class__.__init__.__globals__ }}"
    post_input = GuardResult(text=text, action="pass", findings=(), phase="post_process")

    out = await inspector.inspect(post_input)

    assert len(out.findings) >= 1


@pytest.mark.asyncio
async def test_findings_are_independent_per_phase_invocation() -> None:
    """Calling inspect() twice on the same content (once per phase) produces
    two separate sets of findings, each tagged with its own phase."""
    inspector = TemplateInjectionInspector(phases={"pre_process", "post_process"})
    text = "{{ config.__class__ }}"

    pre_in = GuardResult(text=text, action="pass", findings=(), phase="pre_process")
    post_in = GuardResult(text=text, action="pass", findings=(), phase="post_process")

    pre_out = await inspector.inspect(pre_in)
    post_out = await inspector.inspect(post_in)

    assert len(pre_out.findings) >= 1
    assert len(post_out.findings) >= 1
    assert pre_out.phase == "pre_process"
    assert post_out.phase == "post_process"
