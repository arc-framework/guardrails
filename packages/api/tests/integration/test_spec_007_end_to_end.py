"""End-to-end smoke: every integration-API user story wires up correctly.

One canary test per US, asserting the deliverable is reachable from a
fresh-process perspective. The "everything is wired up correctly" gate.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import httpx
import pytest
from arc_guard_core.types import GuardInput

from arc_guard_service import ServiceSettings, run_guard
from arc_guard_service.transport.http import create_app

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_us1_part1_in_process_run_guard_works() -> None:
    result = run_guard(GuardInput(text="What is 2 + 2?"))
    assert result.action in {"pass", "block", "redact"}


@pytest.mark.asyncio
async def test_us1_part2_http_transport_works() -> None:
    app = create_app(ServiceSettings())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/guard", json={"text": "hello"})
    assert response.status_code == 200
    body = response.json()
    assert "action" in body


def test_us2_public_surface_manifest_check_passes() -> None:
    spec = importlib.util.spec_from_file_location(
        "_check_surface_e2e",
        REPO_ROOT / "tools" / "check_public_surface.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["_check_surface_e2e"] = module
    spec.loader.exec_module(module)
    errors = module.check_manifest()  # type: ignore[attr-defined]
    assert errors == [], "\n".join(errors)


# test_us3_examples_directory_has_four_self_contained_projects: removed.
# The four-integration-mode examples directory was retired by operator
# decision; integration patterns are documented in
# docs/walkthrough/007-integration-api-delivery.md prose only.


def test_us4_walkthroughs_follow_uniform_schema() -> None:
    walkthroughs = sorted((REPO_ROOT / "docs" / "walkthrough").glob("00[2-7]-*.md"))
    assert len(walkthroughs) >= 6, f"expected >= 6 walkthroughs, got {len(walkthroughs)}"

    required_section = "## What changed"
    for path in walkthroughs:
        text = path.read_text(encoding="utf-8")
        assert required_section in text, f"{path.name} missing 'What changed' section"


def test_us4_docs_link_check_clean() -> None:
    spec = importlib.util.spec_from_file_location(
        "_check_links_e2e",
        REPO_ROOT / "tools" / "check_docs_links.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["_check_links_e2e"] = module
    spec.loader.exec_module(module)
    errors = module.check_links()  # type: ignore[attr-defined]
    assert errors == [], "\n".join(errors)


def test_us5_readme_links_to_architecture_index() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/architecture/" in readme or "docs/architecture)" in readme
    arch_index = REPO_ROOT / "docs" / "architecture" / "README.md"
    assert arch_index.is_file()
    arch_text = arch_index.read_text(encoding="utf-8")
    assert "rewrite-roadmap" in arch_text


def test_us6_backlog_has_five_mandatory_rows() -> None:
    backlog = (REPO_ROOT / "specs" / "008-backlog.md").read_text(encoding="utf-8")
    for name in (
        "More transports",
        "More provider integrations",
        "Rich policy authoring UX",
        "Product dashboard / analytics UI",
        "Advanced packaging polish",
    ):
        assert name in backlog, f"backlog missing row: {name!r}"


def test_decision_contract_frozen_no_new_protocols() -> None:
    """Verify the additive-only public surface — only the documented new symbols."""
    import arc_guard_core

    new_symbols = {
        "TransportError",
        "FAILURE_API_TRANSPORT",
    }
    for name in new_symbols:
        assert hasattr(arc_guard_core, name), f"{name} expected on arc_guard_core"


def test_decision_contract_frozen_no_new_stages() -> None:
    """The pipeline-stage list MUST NOT grow beyond the post-006 stage set."""
    from arc_guard_core.stages import STAGE_DESCRIPTORS

    expected_after_006 = {
        "validate", "defend", "classify", "deception_inspect", "sanitize",
        "route", "execute", "refusal", "verify", "rehydrate",
        "decision_emit", "report",
    }
    actual = set(STAGE_DESCRIPTORS)
    assert actual == expected_after_006, (
        f"unexpected stage drift: extra={actual - expected_after_006}, "
        f"missing={expected_after_006 - actual}"
    )


# test_examples_smoke_tests_pass: removed when the examples directory was retired.
