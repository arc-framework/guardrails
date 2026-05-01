# Quickstart — Rewrite Foundation

Two walkthroughs that exercise the contracts above end-to-end. The first targets **integrators** (User Story 1, 4); the second targets **contributors** (User Stories 2, 3, 5). Each one is a runnable script that the contract test suite executes after the migration lands.

---

## Walkthrough A — Integrator: install `core`, run a benign guard call

**Validates User Story 1 acceptance scenarios 1, 2, 3 and User Story 4 acceptance scenario 1.**

### A.1 Fresh environment

```bash
mkdir /tmp/arc-quickstart && cd /tmp/arc-quickstart
uv venv --python 3.11
source .venv/bin/activate
```

### A.2 Install `core` only

```bash
# Install from the local workspace path; replace with PyPI URL once published
uv pip install --no-deps "arc-guard-core @ file:///$HOME/Workspace/arc/sdk/packages/core"
uv pip install pydantic  # the only runtime dep
```

### A.3 Audit the install closure (SC-002)

```bash
uv pip list
```

Expected output contains exactly two non-stdlib packages:

```
pydantic        2.x
arc-guard-core  0.1.0
```

If `presidio-analyzer`, `nats-py`, `UnleashClient`, `httpx`, `opentelemetry-*`, `torch`, or `transformers` appears, **the import-graph audit has failed**. Re-run `tools/check_dependency_tree.py`.

### A.4 Run a pass-through guard call

```python
# /tmp/arc-quickstart/run_guard.py
from arc_guard_core.config import GuardConfig
from arc_guard_core.pipeline import GuardPipeline
from arc_guard_core.types import GuardInput

config = GuardConfig()  # defaults; no inspectors registered yet — Spec 003 wires them
pipeline = GuardPipeline(config=config)

result = pipeline.pre_process_sync(GuardInput(text="hello"))
print(result.action, result.is_clean, result.bypass_reason)
```

Expected:

```
pass True None
```

The benign call completes without ImportError and without loading any adapter, transport, or provider SDK.

### A.5 Confirm no provider modules loaded

```python
import sys
forbidden = {"presidio_analyzer", "nats", "UnleashClient", "httpx", "opentelemetry", "torch", "transformers"}
loaded = forbidden & set(sys.modules)
assert loaded == set(), f"forbidden modules loaded: {loaded}"
```

The assertion succeeds. **User Story 1 acceptance scenarios 1 and 2 pass.**

### A.6 Opt into an adapter via extras

```bash
uv pip install "arc-guard[nats]"
```

Now `arc_guard.adapters.nats_reporter` is importable. `arc_guard_core` is unchanged. **User Story 1 acceptance scenario 3 passes.**

### A.7 Trigger the deprecation shim

```python
import warnings
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    from arc_guard.types import GuardResult  # Spec 001 path
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)
    msg = str(caught[0].message)
    assert "moved to arc_guard_core.types.GuardResult" in msg
    assert "removed in arc-guard 0.3.0" in msg
```

The deprecation warning fires with the replacement and removal version named. **User Story 4 acceptance scenario 1 passes.**

---

## Walkthrough B — Contributor: refactor inside `core`, refactor across boundary, validate failures

**Validates User Story 2 acceptance scenarios 1, 2, 3 and User Story 3 acceptance scenarios 1, 2, 3 and User Story 5 acceptance scenario 1.**

### B.1 Set up the workspace

```bash
cd ~/Workspace/arc/sdk/packages
uv sync
```

### B.2 Run the contract test suite (baseline)

```bash
uv run --package arc-guard-core pytest tests/contract/
```

Expected: all green. The snapshot under `tests/contract/snapshots/` matches the live public surface.

### B.3 Refactor an internal helper (US 2.1)

```bash
# Rename a private helper inside core
sed -i '' 's/_compute_max_risk/_compute_aggregate_risk/g' \
    src/arc_guard_core/types.py tests/unit/test_types.py
uv run --package arc-guard-core pytest tests/contract/
```

Expected: all green. **User Story 2 acceptance scenario 1 passes** — internal renames do not affect the contract.

### B.4 Add an additive optional field (US 2.2)

```bash
# Add `note: str | None = None` to GuardResult
$EDITOR src/arc_guard_core/types.py
uv run --package arc-guard-core pytest tests/contract/
```

Expected: the test reports the additive change and *fails* with a message like:

```
public_types: additive change detected (GuardResult.note added). Update CHANGELOG.md.
```

Adding the CHANGELOG entry causes the next run to pass. **User Story 2 acceptance scenario 2 passes.**

### B.5 Attempt a breaking rename (US 2.3)

```bash
# Rename GuardResult.text → GuardResult.content
$EDITOR src/arc_guard_core/types.py
uv run --package arc-guard-core pytest tests/contract/
```

Expected: the test fails with:

```
public_types: rename detected (GuardResult.text → GuardResult.content). This is a breaking change. Use the deprecation flow.
```

Reverting the rename makes the test pass. **User Story 2 acceptance scenario 3 passes.**

### B.6 Malformed configuration rejected at load (US 3.1)

```python
# packages/core/tests/unit/test_config.py snippet
import pytest
from pydantic import ValidationError
from arc_guard_core.config import GuardConfig

def test_unknown_field_rejected():
    with pytest.raises(ValidationError) as exc:
        GuardConfig.model_validate({"enabled": True, "unknown_field": 42})
    assert "unknown_field" in str(exc.value)
```

Expected: the test passes — `extra='forbid'` rejects unknown fields. **User Story 3 acceptance scenario 1 passes.**

### B.7 Malformed API request rejected at boundary (US 3.2)

```python
# packages/api/tests/test_request_validation.py snippet
import pytest
from arc_guard_service.routes.guard import validate_request_payload
from arc_guard_core.exceptions import ApiBoundaryValidationError

def test_malformed_request_rejected():
    with pytest.raises(ApiBoundaryValidationError) as exc:
        validate_request_payload({"text": 42})  # text must be a string
    assert exc.value.code.startswith("api.")
    assert "text" in exc.value.details
```

Expected: the test passes. **User Story 3 acceptance scenario 2 passes.**

### B.8 Malformed `Finding` rejected at pipeline contract (US 3.3)

```python
# packages/core/tests/unit/test_pipeline_validation.py snippet
import pytest
from arc_guard_core.exceptions import PipelineContractValidationError
from arc_guard_core.pipeline import _validate_finding  # internal contract helper
from arc_guard_core.types import Finding, RiskLevel

def test_finding_invalid_span_rejected():
    bad = Finding(entity_type="EMAIL", start=10, end=5, risk_level=RiskLevel.LOW, inspector="test")
    with pytest.raises(PipelineContractValidationError) as exc:
        _validate_finding(bad)
    assert exc.value.code == "pipeline.invalid_span"
    assert "start" in exc.value.details
    assert "end" in exc.value.details
```

Expected: the test passes. **User Story 3 acceptance scenario 3 passes.**

### B.9 Try to add a runtime dep without a note (US 5.1)

```bash
# Edit packages/core/pyproject.toml — add `httpx>=0.25` to dependencies
$EDITOR packages/core/pyproject.toml
git add packages/core/pyproject.toml
python tools/check_adopt_vs_build.py
```

Expected output:

```
ERROR: arc-guard-core gained a new runtime dependency 'httpx' but no adopt-vs-build entry references it.
       Add an entry to .specify/memory/libraries.md or specs/002-rewrite-foundation/decisions/<id>.md.
```

Reverting the change passes the check. Adding the entry also passes. **User Story 5 acceptance scenario 1 passes.**

---

## Walkthrough validation summary

| User Story | Acceptance Scenarios | Walkthrough Step |
|---|---|---|
| US 1 — Integrator install | 1, 2, 3 | A.4, A.5, A.6 |
| US 2 — Contract stability | 1, 2, 3 | B.3, B.4, B.5 |
| US 3 — Boundary validation | 1, 2, 3 | B.6, B.7, B.8 |
| US 4 — Deprecation flow | 1 (warning), 2 (removal), 3 (changelog) | A.7 covers (1); (2) and (3) covered by `tests/deprecation/test_legacy_imports.py` and CHANGELOG check in CI |
| US 5 — Adopt-vs-build | 1, 2 | B.9 covers (1); (2) covered by `tools/check_adopt_vs_build.py --dev-allowed` test |

Edge cases from the spec are exercised by:

- circular-import attempt → `tools/check_import_graph.py` test fixture.
- async-blocking regression → `tools/check_async_blocking.py` test fixture.
- adapter import from `core` → `tools/check_import_graph.py` test fixture.
- deprecated path post-removal → `tests/deprecation/test_post_removal.py` (set the test's `removal_version` fixture).

Each fixture is wired in tasks generated by `/speckit.tasks`.
