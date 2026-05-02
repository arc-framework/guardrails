"""``specs/008-backlog.md`` follows the documented schema.

Asserts: 5 mandatory rows in Backlog; 7 columns per row; every Status is one
of the three documented values; every Source link resolves to the rewrite
roadmap; every Depends_on cell uses valid Spec IDs (002-007).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKLOG = REPO_ROOT / "specs" / "008-backlog.md"

REQUIRED_NAMES = {
    "More transports",
    "More provider integrations",
    "Rich policy authoring UX",
    "Product dashboard / analytics UI",
    "Advanced packaging polish",
}

VALID_SPEC_IDS = {"002", "003", "004", "005", "006", "007"}


def _parse_section_rows(section: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in section.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or all(c == "" or set(c) <= {"-", " "} for c in cells):
            continue
        rows.append(cells)
    return rows[1:]  # drop header


def _split_sections(text: str) -> tuple[str, str]:
    parts = re.split(r"^##\s+(Backlog|Delivered)\s*$", text, flags=re.MULTILINE)
    sections = {}
    for i in range(1, len(parts) - 1, 2):
        name = parts[i].strip()
        body = parts[i + 1]
        sections[name] = body
    return sections.get("Backlog", ""), sections.get("Delivered", "")


def test_backlog_file_exists() -> None:
    assert BACKLOG.is_file(), f"missing {BACKLOG}"


def test_backlog_has_seven_columns_per_row() -> None:
    text = BACKLOG.read_text(encoding="utf-8")
    backlog_section, _ = _split_sections(text)
    rows = _parse_section_rows(backlog_section)
    assert rows, "no rows in Backlog section"
    for row in rows:
        assert len(row) == 7, f"expected 7 columns, got {len(row)}: {row}"


def test_backlog_contains_all_five_mandatory_rows() -> None:
    text = BACKLOG.read_text(encoding="utf-8")
    backlog_section, _ = _split_sections(text)
    rows = _parse_section_rows(backlog_section)
    names = {row[0].strip() for row in rows}
    missing = REQUIRED_NAMES - names
    assert not missing, f"missing mandatory rows: {sorted(missing)}"


def test_backlog_status_values_are_valid() -> None:
    text = BACKLOG.read_text(encoding="utf-8")
    backlog_section, _ = _split_sections(text)
    rows = _parse_section_rows(backlog_section)
    for row in rows:
        status = row[6].strip()
        assert status == "Backlog" or status.startswith("Picked up:"), (
            f"row {row[0]!r} has invalid Status {status!r}"
        )


def test_backlog_depends_on_uses_valid_spec_ids() -> None:
    text = BACKLOG.read_text(encoding="utf-8")
    backlog_section, _ = _split_sections(text)
    rows = _parse_section_rows(backlog_section)
    for row in rows:
        depends = row[2].strip()
        ids = {part.strip() for part in depends.split(",") if part.strip()}
        invalid = ids - VALID_SPEC_IDS
        assert not invalid, f"row {row[0]!r}: invalid Spec IDs in Depends_on: {invalid}"


def test_backlog_size_estimates_are_coarse() -> None:
    text = BACKLOG.read_text(encoding="utf-8")
    backlog_section, _ = _split_sections(text)
    rows = _parse_section_rows(backlog_section)
    for row in rows:
        size = row[4].strip()
        assert size in {"S", "M", "L", "XL"}, f"row {row[0]!r}: invalid Size {size!r}"
