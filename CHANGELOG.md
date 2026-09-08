# Changelog

## [Unreleased]

### Added
- PG201 — flag blanket `# noqa` with no codes listed.
- PG202 — flag broad `# noqa` listing 3+ PG/PYD codes on one line.
- PG203 — flag `# noqa: PGxxx` / `# noqa: PYDxxx` without a matching
  entry under `[tool.pydantic_guidance.suppressions]` in
  `pyproject.toml`.
- PG204 — flag registry entries whose target construct no longer
  triggers the listed code.
- PG205 — flag project settings (`per-file-ignores`, `extend-ignore`,
  inline `# flake8:`) disabling PG/PYD codes.
- Suppression registry loaded eagerly from `pyproject.toml`; FQN
  derived from AST identifiers (functions, methods, nested classes,
  module scope).

### Changed
- `PGPlugin` dispatches per file kind: AST scanner for `.py` / `.pyi`,
  config scanner for `.toml` / `.cfg` / `.ini` / `.flake8`.

### Required Human Gate
- Registry edits require `CODEOWNERS`-gated human review on
  `pyproject.toml`. Agents must not bypass this gate.
