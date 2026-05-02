"""``RefusalCode.FIDELITY_DROP`` has a real default template registered."""

from __future__ import annotations

from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.refusal.templates import get_refusal_template


def test_fidelity_drop_template_is_real_not_stub() -> None:
    template = get_refusal_template(RefusalCode.FIDELITY_DROP)
    assert template.human_message, "FIDELITY_DROP human_message must be non-empty"
    assert "reserved" not in template.human_message.lower(), (
        "FIDELITY_DROP template must not be the historical placeholder stub"
    )
    assert template.next_steps, "FIDELITY_DROP next_steps must be non-empty"
    assert isinstance(template.next_steps, tuple)
