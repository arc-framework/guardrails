"""Smoke test: ``batch.py`` reads JSONL and writes JSONL."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_batch_produces_one_output_per_input(tmp_path: Path) -> None:
    here = Path(__file__).resolve().parents[1]
    inputs = here / "inputs.jsonl"
    output = tmp_path / "out.jsonl"
    subprocess.run(
        [sys.executable, str(here / "batch.py"), str(inputs), "--output", str(output)],
        check=True,
    )
    in_lines = inputs.read_text().strip().splitlines()
    out_lines = output.read_text().strip().splitlines()
    assert len(out_lines) == len(in_lines), (
        f"expected {len(in_lines)} output rows, got {len(out_lines)}"
    )
    for row in out_lines:
        parsed = json.loads(row)
        assert "action" in parsed
        assert parsed["action"] in {"pass", "block", "redact", "hash", "tokenize"}
