# Changelog — arc-guard-service

All notable changes to the `arc-guard-service` package are documented here. Format follows Keep a Changelog; this package adheres to Semantic Versioning.

## [0.1.0] — 2026-05-01

### Added
- Initial scaffold. Spec 002 ships package skeleton only; Spec 007 owns full deployment surface (route handlers, DI wiring, integration docs).
- API-boundary request validator producing typed `ApiBoundaryValidationError`.
- Settings skeleton via `pydantic-settings`.
