@.specify/memory/constitution.md

# arc-sdk Claude context

## Repo focus

- The live code packages are `python/arc-guardrails` and `python/arc-common`.
- The planned package split tracked by Spec `002` is `packages/common`, `packages/core`, and `packages/api`.
- The rewrite planning source of truth lives in `docs/superpowers/specs/2026-05-01-rewrite-roadmap.md`.
- The supporting rewrite rationale lives in `docs/superpowers/specs/2026-05-01-universal-guardrail-revisit.md`.
- `specs/` and `.specify/` define the planning workflow and governance artifacts.
- `docs/walkthrough/` holds one-page summaries per spec and must stay current.
- `.claude/commands/` contains Speckit slash commands for Claude Code workflows.

## Working rules

- Use plan mode first for architecture work, cross-package edits, or spec-driven changes.
- Keep the core package provider-neutral; adapters stay optional and isolated.
- Treat `specs/001-arc-guard-rails/` as the historical pre-rewrite baseline unless a task explicitly updates it.
- Use the rewrite roadmap to derive new specs and sequence work across foundation, must-have, research, and delivery phases.
- Use `uv` for Python workflows and prefer package-local commands from each `pyproject.toml`.
- When public behavior changes, update the matching docs or spec artifacts.
- Update `docs/walkthrough/` when a spec meaning changes materially.
- Refresh generated agent context from the active plan with `scripts/update-speckit-context.sh`.

## Context sources

- Read `.specify/memory/patterns.md` when a task changes contracts, adapters, or usage modes.
- Read `.specify/memory/libraries.md` before adding dependencies.
- `arc-guard-agent-prompts.md` is an analysis prompt pack, not the shared project instruction file.
