"""Refusal-template registry tests."""

from __future__ import annotations

from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.refusal.templates import (
    DEFAULT_REFUSAL_TEMPLATES,
    RefusalTemplate,
    get_refusal_template,
    register_refusal_template,
)


def test_every_code_has_a_default_template() -> None:
    for code in RefusalCode:
        assert code in DEFAULT_REFUSAL_TEMPLATES, f"missing template for {code}"


def test_every_default_human_message_non_empty_or_reserved() -> None:
    for code, tmpl in DEFAULT_REFUSAL_TEMPLATES.items():
        if code is RefusalCode.FIDELITY_DROP_PLACEHOLDER:
            # Reserved (detector not yet implemented); placeholder text is allowed.
            continue
        assert tmpl.human_message, f"empty human_message for {code}"


def test_register_refusal_template_overrides() -> None:
    new_tmpl = RefusalTemplate(human_message="custom", next_steps=("a",))
    register_refusal_template(RefusalCode.POLICY_BLOCK, new_tmpl)
    assert get_refusal_template(RefusalCode.POLICY_BLOCK) is new_tmpl
    # Restore default to keep test isolation
    register_refusal_template(
        RefusalCode.POLICY_BLOCK,
        DEFAULT_REFUSAL_TEMPLATES[RefusalCode.POLICY_BLOCK],
    )
