.PHONY: corpus-validate corpus-stats

corpus-validate:
	uv run --package arc-guard-service python -m arc_guard_service.examples_loader --validate

corpus-stats:
	uv run --package arc-guard-service python -m arc_guard_service.examples_loader --stats
