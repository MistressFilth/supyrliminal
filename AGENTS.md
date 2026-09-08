# AGENTS.md — pydantic-guidance

Repository memory for LLM agents working on this codebase.

## Local-only memory file

@AGENTS.local.md

## What this repo is

`pydantic-guidance` is a flake8 extension that steers Pydantic code toward
documented best practices. It is boundary-aware and ships as a flake8 entry
point plus a standalone CLI for the suppression-audit codes that cannot be
reached via flake8's AST plugin protocol.

## Codes

| Range  | Scope | Emitter | Status |
|--------|-------|---------|--------|
| PG001-PG003 | TypeAdapter placement, deprecated validators, BaseModel surface | flake8 (`PGPlugin`) | hard, default-on |
| PG101 | `BaseModel` subclass with no Pydantic surface | flake8 (`PGPlugin`) | advisory, opt-in via `--extend-select=PG101` |
| PG201 | Blanket `# noqa` with no codes listed | flake8 (`PGPlugin`) | hard, default-on |
| PG202 | `# noqa` listing 3+ PG/PYD codes | flake8 (`PGPlugin`) | hard, default-on |
| PG203 | `# noqa: PGxxx` / `# noqa: PYDxxx` without a registry entry | flake8 (`PGPlugin`) | hard, default-on |
| PG204 | Registry entry whose target construct no longer triggers the listed code | flake8 (`PGPlugin`) | hard, default-on |
| PG205 | Project settings disable a PG/PYD code (`per-file-ignores`, `extend-ignore`, inline `# flake8:`) | `pg-scan-config` CLI | hard, default-on |

PG205 lives in a separate CLI because flake8's AST plugin protocol calls
`ast.parse()` first and never instantiates the plugin for `.toml`/`.cfg`/
`.ini` files. The CLI entry point is `pg-scan-config`.

## Suppression scanner

The scanner lives in `pydantic_guidance/_suppression_scanner.py`. It is
pure: takes a parsed AST, the source string, and a registry, returns
`GuidanceFinding` objects. It does not load the registry or talk to
flake8 — `flake8_guidance.PGPlugin` wires those.

The registry model (`SuppressionEntry`, `SuppressionRegistry`) lives in
`pydantic_guidance/_models.py`. Entries are keyed by `(fqn, code)` and
duplicate pairs are rejected at construction time. FQN keys are
AST-stable: `module`, `module.func`, `module.Class.method`,
`module.Class.Nested`. They never encode line numbers, so editing a
construct below an existing one does not invalidate the registry.

FQN resolution is in `pydantic_guidance/_fqn.py`. The
`FQNResolver(tree, module).for_line(line)` API walks the parent map and
returns the smallest enclosing construct for a given line.

The PG204 scanner (`scan_stale_registry`) needs the AST to do per-construct
matching — collapsing analyzer findings to a code-set would let a stale
entry pass whenever a different construct in the same file fired the same
code. When the AST is unavailable, it falls back to module-level matching.

## Project-settings scanner (PG205)

Lives in `pydantic_guidance/_config_scanner.py` (pure functions) and
`pydantic_guidance/_pg205_cli.py` (CLI entry point). The CLI walks the
project, identifies the active settings file by filename
(`pyproject.toml`, `setup.cfg`, `.flake8`, `tox.ini`), and delegates to
`scan_config` which dispatches on that filename rather than file suffix.

## Pre-PR checklist

Before opening or merging a PR, the agent MUST:

1. **Keep versioning bumps adherent to SemVer.** Bump the appropriate
   segment for the nature of the change (major / minor / patch). Update
   every version surface listed in `@~/.claude/rules/versioning.md` —
   for this repo, the relevant surfaces are `pyproject.toml` (PEP 440)
   and the git tag + CHANGELOG heading (SemVer).
2. **Keep `CHANGELOG.md` up to date.** Add an entry under the
   `[Unreleased]` section describing the change.
3. **Keep `README.md` up to date.** New commands, new config options,
   new install steps, behavior changes — all reflected in the README.
4. **Keep any `docs/` up to date.** If the repo has a `docs/`
   directory, the change is reflected there as well.

## Pre-existing issues

Treat any "pre-existing" issue — one already on `main`, in the issue
tracker, or referenced in TODO/FIXME/XXX — as if it is your own issue
to solve. Do not dismiss as out-of-scope, historical, or someone else's
problem. The first encounter is yours; resolve or escalate.

## Required human gate on the registry

Edits to `[tool.pydantic_guidance.suppressions]` in `pyproject.toml`
require `CODEOWNERS`-gated human review. Agents must not bypass this
gate by reformatting or rewriting registry content without review.

## Commit conventions

All commits follow Conventional Commits v1.0.0. Subject only.
No `Co-Authored-By:` trailers, no `Generated with Claude Code`
attribution. `.pre-commit-config.yaml` enforces the trailer ban.

## Project conventions

- `src/` is not used; the package source lives in `pydantic_guidance/`
  at the repo root.
- `tests/` is a sibling to the package source. `tests/unit/` holds unit
  tests; `tests/features/` holds behavior tests (pytest-bdd).
- `docs/` contains user-facing documentation; update alongside
  behavior changes.
- Run the four quality gates before declaring work done:
  - `.venv/bin/python -m pytest tests/ -q`
  - `.venv/bin/python -m mypy pydantic_guidance tests/features/`
  - `uvx ruff format --check .`
  - `uvx ruff check .`

## References

- Makefile targets: `@Makefile`
- Pre-commit hooks: `@.pre-commit-config.yaml`
- CHANGELOG format: `@~/.claude/rules/changelog.md`
- Versioning surfaces: `@~/.claude/rules/versioning.md`
- Required files inventory: `@~/.claude/rules/required-files.md`
- Repository layout: `@~/.claude/rules/repository-layout.md`
