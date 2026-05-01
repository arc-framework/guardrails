"""T061 — regression test for the async-blocking lint."""

from __future__ import annotations

import sys
from pathlib import Path

# Make tools/ importable.
TOOLS = Path(__file__).resolve().parents[3].parent / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import check_async_blocking as cab  # noqa: E402

CLEAN_SAMPLE = """
import asyncio

async def good():
    await asyncio.sleep(0)
    await asyncio.to_thread(_blocking)

def _blocking():
    import time
    time.sleep(0.1)
"""

DIRTY_SAMPLE = """
import time

async def bad():
    time.sleep(0.1)        # blocking call inside async function
    return 1
"""


def test_clean_async_function_passes(tmp_path: Path) -> None:
    f = tmp_path / "clean.py"
    f.write_text(CLEAN_SAMPLE)
    findings = cab._scan_file(f)
    assert findings == [], f"expected no findings, got {findings}"


def test_blocking_call_in_async_is_flagged(tmp_path: Path) -> None:
    f = tmp_path / "dirty.py"
    f.write_text(DIRTY_SAMPLE)
    findings = cab._scan_file(f)
    assert any("time.sleep" in call for _line, call in findings)


def test_workspace_has_no_async_blocking_regressions() -> None:
    """Sanity check — the live core/pip source must already be clean."""
    rc = cab.main([])
    assert rc == 0, "async-blocking regression detected in core/pip src"


def test_asyncio_to_thread_wrapper_is_accepted(tmp_path: Path) -> None:
    """asyncio.to_thread is an explicit opt-out and must not be flagged."""
    src = """
import asyncio
import time

async def wrapped():
    await asyncio.to_thread(time.sleep, 0.1)
"""
    f = tmp_path / "wrapped.py"
    f.write_text(src)
    findings = cab._scan_file(f)
    # The blocking call inside asyncio.to_thread is allowed.
    assert findings == []
