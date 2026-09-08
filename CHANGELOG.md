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
- `pg-scan-config` standalone CLI for PG205 (flake8's AST plugin
  protocol cannot reach `.toml`/`.cfg`/`.ini` files).

### Changed
- `PGPlugin` emits only the AST-scannable codes (PG001-PG003, PG101,
  PG201-PG204); PG205 moved to a dedicated CLI entry point.
- `scan_config` now dispatches by recognized filename rather than
  suffix; accepts the TOML list form of `per-file-ignores` and
  `extend-ignore`.

### Required Human Gate
- Registry edits require `CODEOWNERS`-gated human review on
  `pyproject.toml`. Agents must not bypass this gate.
