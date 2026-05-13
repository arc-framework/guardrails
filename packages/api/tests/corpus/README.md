# Swagger prompt corpus

This directory feeds the request-body example dropdown on `POST /v1/chat/completions` in Swagger UI.

## Layout

- `prompts/{inspector}__{difficulty}__{nn}.yaml` — one prompt per file
- `knowledge_base/*.md` — fictional ARC company referenced by hard prompts (see `knowledge_base/README.md`)
- `_template.yaml` — copy this to start a new prompt

## Adding a prompt

1. Pick an inspector (one of: `pii_presidio`, `prompt_injection`, `jailbreak_heuristic`, `jailbreak_ml`, `deception`, `semantic_policy`, `code_injection_sql`, `code_injection_shell`, `code_injection_template`).
2. Pick a difficulty: `easy`, `medium`, `super_hard`.
3. Find the next free `nn` (no gaps allowed).
4. Copy `_template.yaml` to `prompts/{inspector}__{difficulty}__{nn}.yaml` and fill it in.
5. Validate: `make corpus-validate`.
6. Coverage check: `make corpus-stats`.

## Cross-rules

- `id` must equal the filename stem.
- `expected.refusal_code` must be set iff `expected.action == "block"`.
- `nn` numbering starts at `01` and has no gaps.
- For each `(inspector, super_hard)` bucket of 5, **exactly two** prompts must have `false_positive: true`.

## Schema

See `arc_guard_service.examples_loader.CorpusPrompt`.

## Running locally with a live backend

`OLLAMA_BASE_URL=http://localhost:11434 uv run pytest tests/contract/test_corpus_outcomes.py`
