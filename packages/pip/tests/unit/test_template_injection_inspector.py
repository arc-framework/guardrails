"""Unit tests for TemplateInjectionInspector."""

from __future__ import annotations

from typing import Any

import pytest
from arc_guard_core.types import GuardResult

from arc_guard.inspectors.code_injection.template import (
    TemplateInjectionInspector,
)


class _RecordingLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def bind(self, **fields: Any) -> _RecordingLogger:
        return self

    def event(self, name: str, *, level: str = "info", **fields: Any) -> None:
        self.events.append((name, {"level": level, **fields}))


def _post_result(text: str) -> GuardResult:
    return GuardResult(text=text, action="pass", findings=(), phase="post_process")


async def _inspect(
    inspector: TemplateInjectionInspector, text: str
) -> GuardResult:
    return await inspector.inspect(_post_result(text))


@pytest.mark.asyncio
async def test_detects_jinja_dunder_traversal() -> None:
    inspector = TemplateInjectionInspector()
    out = await _inspect(
        inspector,
        "Hello {{ config.__class__.__init__.__globals__ }} world",
    )
    subtypes = {f.entity_type for f in out.findings}
    assert "template.sandbox_escape" in subtypes


@pytest.mark.asyncio
async def test_detects_jinja_block_dunder_traversal() -> None:
    inspector = TemplateInjectionInspector()
    out = await _inspect(
        inspector,
        "{% for cls in ''.__class__.__mro__[1].__subclasses__() %}{% endfor %}",
    )
    subtypes = {f.entity_type for f in out.findings}
    assert "template.sandbox_escape" in subtypes


@pytest.mark.asyncio
async def test_benign_jinja_documentation_passes() -> None:
    inspector = TemplateInjectionInspector()
    out = await _inspect(
        inspector,
        "Use Jinja sigils like {{ name }} or {% if x %}...{% endif %} in templates.",
    )
    assert out.findings == ()


@pytest.mark.asyncio
async def test_detects_script_tag() -> None:
    inspector = TemplateInjectionInspector()
    out = await _inspect(
        inspector,
        "Hi <script>alert(1)</script> bye",
    )
    subtypes = {f.entity_type for f in out.findings}
    assert "template.active_html" in subtypes


@pytest.mark.asyncio
async def test_detects_iframe_and_svg_tags() -> None:
    inspector = TemplateInjectionInspector()
    out = await _inspect(
        inspector,
        "<iframe src='x'></iframe><svg onload='alert(1)'></svg>",
    )
    subtypes = {f.entity_type for f in out.findings}
    assert "template.active_html" in subtypes


@pytest.mark.asyncio
async def test_detects_event_handler_attribute() -> None:
    inspector = TemplateInjectionInspector()
    out = await _inspect(
        inspector,
        "<div onclick='steal()'>",
    )
    subtypes = {f.entity_type for f in out.findings}
    assert "template.active_html" in subtypes


@pytest.mark.asyncio
async def test_detects_javascript_url() -> None:
    inspector = TemplateInjectionInspector()
    out = await _inspect(
        inspector,
        "Visit javascript:alert(1) for fun",
    )
    subtypes = {f.entity_type for f in out.findings}
    assert "template.active_html" in subtypes


@pytest.mark.asyncio
async def test_detects_data_text_html_url() -> None:
    inspector = TemplateInjectionInspector()
    out = await _inspect(
        inspector,
        "Open data:text/html,<script>alert(1)</script>",
    )
    subtypes = {f.entity_type for f in out.findings}
    assert "template.active_html" in subtypes


@pytest.mark.asyncio
async def test_benign_html_prose_passes() -> None:
    inspector = TemplateInjectionInspector()
    out = await _inspect(
        inspector,
        "The <p> tag is the paragraph element. <em>Emphasis</em> is fine.",
    )
    assert out.findings == ()


@pytest.mark.asyncio
async def test_oversize_input_emits_observability_event_and_no_finding() -> None:
    logger = _RecordingLogger()
    inspector = TemplateInjectionInspector(max_input_chars=64, logger=logger)
    text = "{{ config.__class__ }} <script>alert(1)</script>" + ("x" * 200)
    out = await _inspect(inspector, text)
    assert out.findings == ()
    names = [name for name, _ in logger.events]
    assert "guard.code_injection.unparseable_input" in names


@pytest.mark.asyncio
async def test_pre_process_phase_skipped_by_default() -> None:
    inspector = TemplateInjectionInspector()
    pre = GuardResult(
        text="{{ config.__class__.__init__ }}",
        phase="pre_process",
    )
    out = await inspector.inspect(pre)
    assert out.findings == ()


@pytest.mark.asyncio
async def test_capture_raw_matches_default_off() -> None:
    inspector = TemplateInjectionInspector()
    out = await _inspect(inspector, "<script>alert(1)</script>")
    for finding in out.findings:
        assert "raw_match" not in finding.metadata
        assert "fingerprint" in finding.metadata


@pytest.mark.asyncio
async def test_capture_raw_matches_true_includes_raw_match() -> None:
    inspector = TemplateInjectionInspector(capture_raw_matches=True)
    out = await _inspect(inspector, "<script>alert(1)</script>")
    assert any("raw_match" in f.metadata for f in out.findings)
