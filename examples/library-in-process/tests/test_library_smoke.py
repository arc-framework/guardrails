"""Smoke test: ``main.py`` produces the expected output shapes."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_main_prints_expected_output() -> None:
    main_py = Path(__file__).resolve().parents[1] / "main.py"
    result = subprocess.run(
        [sys.executable, str(main_py)],
        capture_output=True,
        text=True,
        check=True,
    )
    out = result.stdout
    assert "benign" in out
    assert "action=pass" in out
    assert "jailbreak" in out
    assert "action=block" in out
    assert "refusal=jailbreak_strong" in out
