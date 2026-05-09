"""Contract test: SQL_INJECTION / SHELL_INJECTION / TEMPLATE_INJECTION codes
+ default templates are pre-registered and resolvable."""

from __future__ import annotations

import pytest

from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.refusal.templates import RefusalTemplate, get_refusal_template


@pytest.mark.parametrize(
    "code,value",
    [
        (RefusalCode.SQL_INJECTION, "sql_injection"),
        (RefusalCode.SHELL_INJECTION, "shell_injection"),
        (RefusalCode.TEMPLATE_INJECTION, "template_injection"),
    ],
)
def test_new_codes_are_present_with_documented_values(code: RefusalCode, value: str) -> None:
    assert isinstance(code, RefusalCode)
    assert str(code) == value


@pytest.mark.parametrize(
    "code",
    [
        RefusalCode.SQL_INJECTION,
        RefusalCode.SHELL_INJECTION,
        RefusalCode.TEMPLATE_INJECTION,
    ],
)
def test_default_template_is_registered(code: RefusalCode) -> None:
    template = get_refusal_template(code)
    assert isinstance(template, RefusalTemplate)
    assert template.human_message
    assert len(template.next_steps) >= 1


def test_sql_template_mentions_sql() -> None:
    msg = get_refusal_template(RefusalCode.SQL_INJECTION).human_message.lower()
    assert "sql" in msg


def test_shell_template_mentions_shell() -> None:
    msg = get_refusal_template(RefusalCode.SHELL_INJECTION).human_message.lower()
    assert "shell" in msg


def test_template_template_mentions_template() -> None:
    msg = get_refusal_template(RefusalCode.TEMPLATE_INJECTION).human_message.lower()
    assert "template" in msg
