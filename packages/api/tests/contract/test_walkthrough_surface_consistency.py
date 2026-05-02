"""Every name in a walkthrough's 'Public surface' section appears in the manifest.

Parses each walkthrough's "Public surface" section, collects backtick-wrapped
identifiers from the table, and asserts each appears in
``docs/public-surface.md`` as a manifest entry.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
WALKTHROUGH_DIR = REPO_ROOT / "docs" / "walkthrough"
MANIFEST = REPO_ROOT / "docs" / "public-surface.md"

_SECTION_PATTERN = re.compile(
    r"##\s+Public surface\s*\n(.*?)(?=\n##\s|\Z)",
    re.DOTALL,
)
_BACKTICK_NAME_PATTERN = re.compile(r"`([A-Za-z_][A-Za-z0-9_.]*)`")


def _walkthrough_paths() -> list[Path]:
    return sorted(WALKTHROUGH_DIR.glob("0??-*.md"))


def _manifest_names() -> set[str]:
    text = MANIFEST.read_text(encoding="utf-8")
    pattern = r"^- name:\s+([A-Za-z_][A-Za-z0-9_]*)"
    return {m.group(1) for m in re.finditer(pattern, text, re.MULTILINE)}


@pytest.mark.parametrize("walkthrough", _walkthrough_paths(), ids=lambda p: p.name)
def test_walkthrough_public_surface_names_in_manifest(walkthrough: Path) -> None:
    text = walkthrough.read_text(encoding="utf-8")
    section_match = _SECTION_PATTERN.search(text)
    if section_match is None:
        pytest.skip(f"{walkthrough.name} has no 'Public surface' section")

    section = section_match.group(1)
    names = {m.group(1) for m in _BACKTICK_NAME_PATTERN.finditer(section)}

    manifest_names = _manifest_names()

    # Allow-list: known sub-module symbols + enum members + module paths.
    # Includes every RefusalCode member and known sub-package class names that
    # are NOT in the top-level package __all__ but are documented in
    # walkthroughs as sub-module exports.
    allowed_extras = {
        # Sub-module functions / methods
        "create_app", "pre_process",
        # RefusalCode members (the enum is in the manifest; members aren't separately listed)
        "API_INVALID_REQUEST", "API_TRANSPORT_TIMEOUT",
        "FIDELITY_DROP", "JAILBREAK", "JAILBREAK_STRONG", "DECEPTION_DRIFT",
        "PII_CRITICAL", "STRATEGY_FAILED", "POLICY_BLOCK",
        "INTERNAL_PIPELINE_ERROR", "INTERNAL_ADAPTER_ERROR",
        "INTERNAL_REFUSAL_BUILD_ERROR", "INTERNAL_ENTITY_PROVIDER_ERROR",
        "INTERNAL_UNKNOWN_ERROR",
        # Sub-module / sub-package classes documented in walkthroughs
        "RuleBasedPolicyRouter", "JailbreakMlBundle", "SemanticBundle",
        "InjectionInspector", "RegistryFrozenError",
    }

    # Strip module-path prefixes (e.g. arc_guard_core.RefusalCode → RefusalCode).
    candidates = {n.split(".")[-1] for n in names}

    # Drop module / sub-module / package names + Python conventions + builtins.
    candidates -= {
        "arc_guard_core", "arc_guard", "arc_guard_service",
        "fastapi", "http", "transport", "pipeline",
        "__all__", "__version__", "__init__",
        "int", "float", "str", "bool", "None", "True", "False",
        "list", "dict", "tuple", "set",
    }

    # Drop lowercase-only identifiers — these are descriptive prose words
    # backticked as code spans (e.g. `low`, `medium`, `high`, `critical`,
    # `stable`, `provisional`, `accept`, `reject`). They are not symbol
    # references; they describe band names / verdicts / states.
    candidates = {n for n in candidates if not n.islower() or "_" in n}

    missing = candidates - manifest_names - allowed_extras

    assert not missing, (
        f"{walkthrough.name}: 'Public surface' references unknown names: {sorted(missing)}"
    )
