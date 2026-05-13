# Releasing arc-guardrails Packages

This guide explains how to publish **arc-guard-core** and **arc-guard** to PyPI.

## Prerequisites

1. **PyPI Account** — Create account at https://pypi.org if you don't have one
2. **Trusted Publisher Setup** (one-time per package):
   - Go to https://pypi.org/project/arc-guard-core/publishing/
   - Click "Add trusted publisher"
   - Select GitHub
   - Owner: `arc-framework` (or your org)
   - Repo: `guardrails`
   - Workflow: `.github/workflows/pypi-publish.yml`
   - Environment: `release`
   - Repeat for `arc-guard` and `arc-guard-service`

That's it. No API tokens needed.

## Release Workflow

### 1. Update Version Numbers

Edit the relevant `pyproject.toml`:

**For arc-guard-core:**
```bash
# packages/core/pyproject.toml
version = "0.10.0"
```

**For arc-guard:**
```bash
# packages/pip/pyproject.toml
version = "0.11.0"
```

### 2. Update CHANGELOG

Add an entry for the new version:

```markdown
## [0.11.0] - 2026-05-14

### Added
- New feature X
- New feature Y

### Fixed
- Bug fix A
- Bug fix B
```

### 3. Commit Changes

```bash
git add packages/pip/pyproject.toml CHANGELOG.md
git commit -m "Release: arc-guard v0.11.0"
git push
```

### 4. Create and Push Tag

The tag format is: `{package}-v{version}`

```bash
# Release arc-guard v0.11.0
git tag pip-v0.11.0
git push --tags
```

Supported tags:
- `core-v0.10.0` → publishes arc-guard-core v0.10.0
- `pip-v0.11.0` → publishes arc-guard v0.11.0
- `service-v0.8.0` → publishes arc-guard-service v0.8.0

### 5. Wait for Validation

GitHub Actions will:
1. Parse the tag (extract package name + version)
2. Verify version in pyproject.toml matches
3. Run full test suite
4. Build distributions (wheel + sdist)
5. **Pause and wait for approval**

You'll see a notice in the workflow run: "Waiting for approval to publish to PyPI"

### 6. Approve and Publish

1. Go to GitHub Actions workflow run
2. Click the `publish` job
3. Click "Review deployments"
4. Select the `release` environment
5. Click "Approve and deploy"

GitHub Actions will then publish to PyPI. The package will be live in ~2-3 minutes.

### 7. Verify

After publishing, verify the package is on PyPI:

```bash
# Check PyPI
pip search arc-guard  # or visit https://pypi.org/project/arc-guard/

# Install it
pip install arc-guard==0.11.0

# Import it
python -c "import arc_guard; print(arc_guard.__version__)"
```

## Troubleshooting

### Tag validation failed
- **"Invalid tag format"** → Use format `{package}-v{version}` (e.g., `pip-v0.11.0`)
- **"Version mismatch"** → Tag version doesn't match pyproject.toml. Update and re-tag.

### Publish blocked
- **"No approval"** → Check the workflow run, click "Review deployments", and approve
- **"Trusted Publisher not configured"** → Set up Trusted Publisher on PyPI first (see Prerequisites)

### Package already exists on PyPI
- PyPI doesn't allow re-uploading the same version. Increment version and retry.

## CI Pipeline

Every push to main runs:
- ✅ Format check (ruff format)
- ✅ Linting (ruff check)
- ✅ Type checking (mypy --strict)
- ✅ Tests (pytest)
- ✅ Build verification (uv build)

All must pass before merging to main. Tagging a commit on main automatically validates and publishes.

## Independent Releases

Each package versions independently:
- **arc-guard-core** moves at its own pace (stable, infrequent releases)
- **arc-guard** moves faster (features, patches)
- **arc-guard-service** is deprioritized (stub)

Example timeline:
```
Week 1: Found a core bug
  → Tag: core-v0.9.1
  → Published, arc-guard stays at v0.11.0

Week 2: New pip feature
  → Tag: pip-v0.11.1
  → Published, arc-guard-core stays at v0.9.1

Week 4: Breaking change
  → Tag: core-v1.0.0
  → Tag: pip-v1.0.0 (requires core>=1.0.0)
```
