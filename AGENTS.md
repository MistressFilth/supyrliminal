# AGENTS.md — supyrliminal

Repository memory for LLM agents working on this codebase.

## Local-only memory file

@AGENTS.local.md

## What this repo is

`supyrliminal` is a flake8 extension that steers Pydantic code toward
documented best practices. It is boundary-aware and ships as a flake8 entry
point plus a CLI umbrella for the suppression-audit code that cannot be
reached via flake8's AST plugin protocol.

The plugin is always on once installed. There is no project config file that
enables or disables it; activation is flake8's job, through `--select` /
`--extend-select` / `# noqa` / `per-file-ignores`.

## Codes

| Range  | Scope | Emitter | Status |
|--------|-------|---------|--------|
| SL001-SL003 | TypeAdapter placement, deprecated validators, BaseModel surface | flake8 (`SLPlugin`) | hard, default-on |
| SL101 | `BaseModel` subclass with no Pydantic surface | flake8 (`SLPlugin`) | advisory, opt-in via `--extend-select=SL101` |
| SL201 | Blanket `# noqa` with no codes listed | flake8 (`SLPlugin`) | hard, default-on |
| SL202 | `# noqa` listing 3+ SL/PYD codes | flake8 (`SLPlugin`) | hard, default-on |
| SL203 | `# noqa: SLxxx` / `# noqa: PYDxxx` without a registry entry | flake8 (`SLPlugin`) | hard, default-on |
| SL204 | Registry entry whose target construct no longer triggers the listed code | flake8 (`SLPlugin`) | hard, default-on |
| SL205 | Project settings disable an SL/PYD code (`per-file-ignores`, `extend-ignore`, inline `# flake8:`) | `supyrliminal scan-config` CLI | hard, default-on |

SL205 lives behind a CLI subcommand because flake8's AST plugin protocol calls
`ast.parse()` first and never instantiates the plugin for `.toml`/`.cfg`/
`.ini` files. The entry point is `supyrliminal scan-config`, with `sl` as a
shorter alias for the same script.

## Suppression scanner

The scanner lives in `supyrliminal/_suppression_scanner.py`. It is pure: takes
a parsed AST, the source string, and a registry, returns `GuidanceFinding`
objects. It does not load the registry or talk to flake8 —
`flake8_supyrliminal.SLPlugin` wires those.

The registry model (`SuppressionEntry`, `SuppressionRegistry`) lives in
`supyrliminal/_models.py`. Entries carry `fqn`, `code`, and `reason`, are keyed
by `(fqn, code)`, and duplicate pairs are rejected at construction time. FQN
keys are AST-stable: `module`, `module.func`, `module.Class.method`,
`module.Class.Nested`. They never encode line numbers, so editing a construct
below an existing one does not invalidate the registry.

FQN resolution is in `supyrliminal/_fqn.py`. The
`FQNResolver(tree, module).for_line(line)` API walks the parent map and returns
the smallest enclosing construct for a given line.

The SL204 scanner (`scan_stale_registry`) needs the AST to do per-construct
matching — collapsing analyzer findings to a code-set would let a stale entry
pass whenever a different construct in the same file fired the same code. When
the AST is unavailable, it falls back to module-level matching.

The registry itself, tracked in `pyproject.toml` under
`[tool.supyrliminal.suppressions]`, is the audit record. `reason` is the
human-facing field; keep it specific enough that a reader can judge the
suppression without reading the code.

## Project-settings scanner (SL205)

Lives in `supyrliminal/_config_scanner.py` (pure functions) and
`supyrliminal/_scan_config_cli.py` (CLI implementation), routed through
`supyrliminal/_cli.py` (argparse umbrella). The CLI walks the project,
identifies the active settings file by filename (`pyproject.toml`, `setup.cfg`,
`.flake8`, `tox.ini`), and delegates to `scan_config`, which dispatches on that
filename rather than file suffix.

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

## Commit conventions

All commits follow Conventional Commits v1.0.0. Subject only.
No `Co-Authored-By:` trailers, no `Generated with Claude Code`
attribution. `.pre-commit-config.yaml` enforces the trailer ban.

## Project conventions

- `src/` is not used; the package source lives in `supyrliminal/` at the
  repo root.
- `tests/` is a sibling to the package source, and `tests/unit/` is the
  whole test tree.
- `docs/` contains user-facing documentation; update alongside
  behavior changes.
- Run the four quality gates before declaring work done:
  - `.venv/bin/python -m pytest tests/ -q`
  - `.venv/bin/python -m mypy supyrliminal`
  - `uvx ruff format --check .`
  - `uvx ruff check .`

## References

- Makefile targets: `@Makefile`
- Pre-commit hooks: `@.pre-commit-config.yaml`
- CHANGELOG format: `@~/.claude/rules/changelog.md`
- Versioning surfaces: `@~/.claude/rules/versioning.md`
- Required files inventory: `@~/.claude/rules/required-files.md`
- Repository layout: `@~/.claude/rules/repository-layout.md`
