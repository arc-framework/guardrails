"""Contract test: a real RefusalTemplate is registered for API_TRANSPORT_TIMEOUT.

Asserts ``get_refusal_template(RefusalCode.API_TRANSPORT_TIMEOUT)`` returns a
populated template (non-empty human message + non-empty next_steps tuple),
not a stub. The template shipped with this code is the operator-facing copy
returned by the HTTP transport on a timeout-triggered refusal envelope.
"""

from __future__ import annotations

from arc_guard_core import RefusalCode
from arc_guard_core.refusal.templates import get_refusal_template


def test_api_transport_timeout_template_registered() -> None:
    template = get_refusal_template(RefusalCode.API_TRANSPORT_TIMEOUT)
    assert template.human_message
    assert "longer" in template.human_message.lower() or "timeout" in template.human_message.lower()
    assert template.next_steps
    assert all(step for step in template.next_steps)
    assert any("retry" in step.lower() or "timeout" in step.lower() for step in template.next_steps)
