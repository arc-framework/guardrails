"""Slow / requires-Docker smoke test: from a clean checkout, `make docker-up`
brings up the full dev stack within 60 seconds, four URLs respond, and
`make docker-nuke` leaves no project containers / volumes / images behind.

Excluded from the default suite (marker filter in pyproject.toml). Run
explicitly with:

    pytest -m 'requires_docker' tests/integration/test_docker_up_quickstart.py

Pre-conditions:
- Docker daemon running.
- Network access (first run pulls llama3.2 ~2GB; pulls cached on subsequent runs).
- Ports 8081, 8766, 11434 free on the host.

The test does NOT exercise the chat endpoint end-to-end (that depends on
the llama3.2 model finishing pulling, which can take minutes on first run).
It only verifies that the bootstrap surfaces the four URLs the spec promises.
"""

from __future__ import annotations

import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

# Repo root: walk up from this file's path until we find the Makefile.
_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = next(
    (p for p in _THIS_FILE.parents if (p / "Makefile").exists()),
    None,
)


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        out = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return out.returncode == 0
    except Exception:
        return False


def _url_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 500
    except urllib.error.HTTPError as e:
        return 200 <= e.code < 500
    except Exception:
        return False


def _wait_for(url: str, *, deadline_s: float) -> bool:
    end = time.monotonic() + deadline_s
    while time.monotonic() < end:
        if _url_ok(url):
            return True
        time.sleep(2.0)
    return False


def _run_make(target: str, *, timeout_s: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["make", target],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )


@pytest.mark.slow
@pytest.mark.requires_docker
@pytest.mark.skipif(_REPO_ROOT is None, reason="repo Makefile not found")
@pytest.mark.skipif(not _docker_available(), reason="docker daemon unavailable")
def test_make_docker_up_brings_stack_online_then_nuke_cleans_everything() -> None:
    up = _run_make("docker-up", timeout_s=900)
    try:
        assert up.returncode == 0, (
            f"`make docker-up` exited {up.returncode}\nstderr:\n{up.stderr[-2000:]}"
        )

        assert _wait_for("http://127.0.0.1:8766/", deadline_s=60), (
            "api root did not respond within 60s"
        )
        assert _wait_for("http://127.0.0.1:8081/", deadline_s=60), (
            "sqlite-ui did not respond within 60s"
        )

        assert _url_ok("http://127.0.0.1:8766/lifecycle/nonexistent-rid"), (
            "lifecycle replay endpoint should return 404 (which counts as ok here)"
        )
        assert _url_ok("http://127.0.0.1:8766/events", timeout=2.0), (
            "events SSE endpoint did not open"
        )
    finally:
        nuke = _run_make("docker-nuke", timeout_s=120)
        assert nuke.returncode == 0, (
            f"`make docker-nuke` exited {nuke.returncode}\nstderr:\n{nuke.stderr[-2000:]}"
        )

    ps = subprocess.run(
        ["docker", "compose", "-f", "packages/api/docker-compose.yml", "ps", "-q"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ps.stdout.strip() == "", f"compose ps not empty after docker-nuke: {ps.stdout!r}"

    vol = subprocess.run(
        ["docker", "volume", "ls", "--format", "{{.Name}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    remaining = vol.stdout.splitlines()
    assert "api_lifecycle-data" not in remaining
    assert "api_ollama-models" not in remaining
