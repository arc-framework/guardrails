# Contributing to arc-guardrails

## Documentation conventions

The repo uses three doc trees with one rule each:

| Where                                                   | What goes there                                                                                                                                                                                   |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`specs/<NNN>-<slug>/`](specs/)                         | Planning artifacts: spec, plan, research, data-model, contracts, tasks, checklists. One directory per feature; never modified after the feature ships unless the spec meaning changes materially. |
| [`docs/`](docs/)                                        | Operator-facing documentation: walkthroughs, the public-surface manifest, the architecture index.                                                                                                 |
| [`docs/architecture/`](docs/architecture/)              | Cross-cutting architecture references: the rewrite roadmap, the universal-guardrail design rationale. Linked from `README.md` as the canonical entry point.                                       |
| [`docs/walkthrough/<NNN>-<slug>.md`](docs/walkthrough/) | One-page per-spec summary. Every walkthrough follows the five-section schema (What changed / Why / Public surface / Operator knobs / References).                                                 |

### Where do I put X?

```
   "I'm writing the spec for a new feature"
       → specs/<NNN>-<slug>/spec.md (use /speckit.specify)

   "I'm writing the operator-facing summary of a spec"
       → docs/walkthrough/<NNN>-<slug>.md (5-section schema)

   "I'm writing a cross-cutting architecture reference"
       → docs/architecture/<slug>.md

   "I'm writing a per-package README"
       → packages/<package>/README.md

   "I'm writing a code-level comment"
       → inline in the source file (informational, never spec-tracking metadata)
```

## Quality gates

- `uv sync --all-packages` resolves the workspace.
- `uv run ruff check packages/`, `uv run mypy` per package, `uv run pytest` per package — all must pass before merge.
- The public-surface check (`tools/check_public_surface.py`) verifies supported
  package-root imports and active deprecation shims stay aligned with the
  manifest.
- The docs-link check (`tools/check_docs_links.py`) verifies internal Markdown links resolve.
- Example smoke tests (`uv run pytest examples/`) verify the four integration-mode examples still boot.

## Commit policy

- Do **not** include `Co-Authored-By:` trailers or AI-attribution citations in commit messages.
- Tracking metadata (Spec NNN, FR-NNN, US-N) belongs in CHANGELOGs and PR descriptions, **never** in source-code comments.
- Comments in code must explain a non-obvious _why_ (a hidden constraint, a workaround, a subtle invariant). If removing the comment wouldn't confuse a future reader, don't write it.

## Spec authoring

New features go through the SpecKit workflow:

1. `/speckit.specify` → `specs/<NNN>-<slug>/spec.md` + a quality checklist.
2. `/speckit.plan` → `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`.
3. `/speckit.tasks` → `tasks.md` with task IDs, parallel markers, story labels.
4. `/speckit.analyze` → drift / coverage / consistency report (read-only).
5. `/speckit.implement` → execute tasks phase by phase.

Every spec must end with a Blast Radius section containing one Mermaid diagram showing what the change touches.
