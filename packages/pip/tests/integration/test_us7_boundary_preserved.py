"""Adding a custom strategy preserves the import-graph boundary contracts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_import_graph_check_passes_after_custom_strategy_registration() -> None:
    """Run the import-graph check as a subprocess (clean process state).

    A custom strategy registered at runtime (in test_us7_custom_strategy.py)
    must not affect the static layered-import contracts. The check operates
    on import edges, not on registry state.
    """
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "tools" / "check_import_graph.py"
    assert script.is_file(), f"missing {script}"
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=repo_root / "packages",
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"import-graph check failed:\n{proc.stdout}\n{proc.stderr}"
    )
    assert "Contracts: 4 kept, 0 broken" in proc.stdout
