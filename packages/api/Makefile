.PHONY: corpus-validate corpus-stats

UV := env -u VIRTUAL_ENV uv

corpus-validate:
	$(UV) run --package arc-guard-service python -m arc_guard_service.examples_loader --validate

corpus-stats:
	$(UV) run --package arc-guard-service python -m arc_guard_service.examples_loader --stats
