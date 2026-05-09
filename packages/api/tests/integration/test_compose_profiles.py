"""Integration: docker-compose profile separation for the sqlite-web DB browser.

The dev profile MUST include the `sqlite-ui` service; the prod profile MUST
NOT. This is the contract that lets operators run `docker compose --profile prod`
in production without exposing a SQL console on port 8081.

Uses `docker compose config` to render the parsed Compose file under each
profile. This does NOT require a running Docker daemon to actually start
containers — just the docker CLI for parsing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE_FILE = REPO_ROOT / "packages" / "api" / "docker-compose.yml"


def _have_docker() -> bool:
    return shutil.which("docker") is not None


pytestmark = pytest.mark.skipif(
    not _have_docker(), reason="docker CLI not available; can't render compose config"
)


def _config_under_profile(profile: str) -> dict:
    """Return the parsed `docker compose config` JSON under the given profile."""
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE_FILE),
            "--profile",
            profile,
            "config",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _services_under_profile(profile: str) -> set[str]:
    return set(_config_under_profile(profile).get("services", {}).keys())


def test_dev_profile_includes_sqlite_ui_service() -> None:
    services = _services_under_profile("dev")
    assert "sqlite-ui" in services, f"dev profile must include sqlite-ui; got {sorted(services)}"


def test_prod_profile_excludes_sqlite_ui_service() -> None:
    services = _services_under_profile("prod")
    assert "sqlite-ui" not in services, (
        f"prod profile must NOT include sqlite-ui; got {sorted(services)}"
    )


def test_both_profiles_include_api_and_ollama() -> None:
    """The api / ollama / ollama-pull services run under BOTH profiles."""
    for profile in ("dev", "prod"):
        services = _services_under_profile(profile)
        for required in ("api", "ollama", "ollama-pull"):
            assert required in services, f"{profile} profile missing required service {required!r}"


def test_dev_profile_sqlite_ui_mounts_lifecycle_data_read_only() -> None:
    """The DB browser MUST mount the lifecycle-data volume read-only so it
    cannot corrupt the data the api is actively writing."""
    cfg = _config_under_profile("dev")
    sqlite_ui = cfg["services"]["sqlite-ui"]
    volumes = sqlite_ui.get("volumes", [])
    # Compose normalizes mounts to a list of dicts with `source`/`target`/`read_only`.
    found_ro_lifecycle = False
    for v in volumes:
        if isinstance(v, dict):
            source = v.get("source", "")
            target = v.get("target", "")
            ro = v.get("read_only", False)
            if "lifecycle-data" in source and target == "/data" and ro:
                found_ro_lifecycle = True
                break
        elif isinstance(v, str):
            # Short-form syntax: "lifecycle-data:/data:ro"
            if "lifecycle-data" in v and "/data" in v and v.endswith(":ro"):
                found_ro_lifecycle = True
                break
    assert found_ro_lifecycle, f"sqlite-ui must mount lifecycle-data:/data:ro; got {volumes!r}"


def test_dev_profile_sqlite_ui_exposes_documented_port() -> None:
    """The browser MUST be served on port 8081 (host) per the documented contract."""
    cfg = _config_under_profile("dev")
    sqlite_ui = cfg["services"]["sqlite-ui"]
    ports = sqlite_ui.get("ports", [])
    found_8081 = False
    for p in ports:
        if isinstance(p, dict):
            if str(p.get("published", "")) == "8081":
                found_8081 = True
                break
        elif isinstance(p, str):
            if "8081:" in p:
                found_8081 = True
                break
    assert found_8081, f"sqlite-ui must publish port 8081; got {ports!r}"


def test_prod_profile_does_not_expose_port_8081() -> None:
    """When prod profile is active, no service should bind port 8081 on the host."""
    cfg = _config_under_profile("prod")
    for service_name, service in cfg["services"].items():
        for p in service.get("ports", []):
            published = p.get("published") if isinstance(p, dict) else None
            if str(published) == "8081":
                pytest.fail(f"prod profile must not expose port 8081; {service_name!r} does")
