# Suppression Scanner — Design

**Date:** 2026-09-07
**Branch:** `feat/suppression-scanner`
**Status:** Draft — awaiting review

## Problem

`pydantic-guidance` (PG) and `flake8-pydantic` (PYD) lint codes are suppressed by the standard flake8 mechanism: `# noqa: PGxxx` and `# noqa: PYDxxx` on the offending line, plus project-wide `per-file-ignores` / `extend-ignore` / inline `# flake8:` blocks. There is no audit surface for those suppressions. An agent (or a hurried engineer) can blanket-suppress a rule, copy-paste a `noqa` onto dozens of lines, or quietly add a code to `per-file-ignores`, and the linter stays silent. The repo loses enforcement without anyone noticing.

A human-in-the-loop (HITL) gate on suppressions exists in spirit (`CODEOWNERS` on `pyproject.toml`) but not in machinery: there is no registry, no completeness check, no way to ask "is this `# noqa` actually authorized?"

## Goal

Surface every PG/PYD suppression, in code and in config, as a first-class flake8 finding. Require an explicit, reviewed registry entry in `pyproject.toml` for every authorized `# noqa: PGxxx` / `noqa: PYDxxx`. Detect blanket and broad suppressions as hard errors. Detect stale registry entries whose target construct no longer triggers the rule. Detect project-settings disabling of PG/PYD codes as hard errors.

The scanner ships as `PG2xx` flake8 codes emitted by the existing `PGPlugin`. Activation is default-on, severity is hard, mirroring `PG001`–`PG003`.

## Non-Goals

- Suppression of codes outside the PG/PYD families. Generic `# noqa: E501` is out of scope.
- Editing or rewriting suppressions automatically. The scanner reports; humans act.
- Replacing `# noqa` with a different mechanism. `# noqa` stays the user-facing knob; the registry is the authorization back-end.
- Enforcing the HITL gate in the linter. The gate is `CODEOWNERS` on `pyproject.toml`, owned outside this repo.

## Codes

All `PG2xx` codes ship default-on and hard, parallel to `PG001`–`PG003`.

| Code | Trigger | Message |
|------|---------|---------|
| `PG201` | `# noqa` with no codes listed | `PG201 blanket # noqa suppresses every rule — list specific codes or remove the line` |
| `PG202` | `# noqa: A,B,C...` listing 3+ PG/PYD codes on one line | `PG202 broad # noqa suppresses N PG/PYD codes — narrow to specific constructs via the registry` |
| `PG203` | `# noqa: PGxxx` / `# noqa: PYDxxx` whose enclosing construct has no matching entry in `[tool.pydantic_guidance.suppressions]` | `PG203 unauthorized # noqa for CODE on CONSTRUCT — add a registry entry under [tool.pydantic_guidance.suppressions] or remove the comment` |
| `PG204` | A registry entry whose target construct does not trigger the listed code | `PG204 registry entry for FQN/CODE is stale — analyzer no longer fires on this construct; remove the entry or re-justify` |
| `PG205` | A project-settings file disables a PG/PYD code (`per-file-ignores`, `extend-ignore`, inline `# flake8:` block) | `PG205 project settings disable CODE in FILE — remove the disable or document it in the registry` |

`PG201` and `PG202` cannot be authorized by the registry: they describe patterns, not constructs. They always fail.

## Registry

Authoritative location: `[tool.pydantic_guidance.suppressions]` in `pyproject.toml`, table-array form so each entry is a self-contained git diff line.

```toml
[[tool.pydantic_guidance.suppressions]]
fqn = "myapp.legacy.parse"
code = "PG001"
reason = "per-call adapter needed; the type is only known inside the function"
approved_by = "alice"
approved_sha = "f3c8d1e"
```

| Field | Required | Notes |
|-------|----------|-------|
| `fqn` | yes | Dotted identifier; see FQN derivation below |
| `code` | yes | One of `PG001`–`PG003`, `PG101`, or any `PYDxxx` |
| `reason` | yes | Human-readable rationale; the `find .pg-approvals` workflow surfaces these in PR review |
| `approved_by` | yes | GitHub handle (or any string); used for audit, not enforcement |
| `approved_sha` | yes | The commit SHA that introduced the entry; ties the registry to a paper trail |

Validation rules:

- `fqn` must parse as a dotted identifier; malformed entries emit a separate `PG206` at parse time (see Future Work).
- `code` must match a known PG/PYD code; unknown codes emit `PG206`.
- Duplicates on `(fqn, code)` are an error (silent override would mask intent).

## FQN Derivation

FQN is the registry key. It is computed from the AST, never from line numbers.

**Module path.** Strip the suffix (`.py`, `.pyi`) and the leading `--pg-config-root` from the file path. Convert `/` to `.`. Remove trailing `.` and `__init__` segments entirely (so a package's `__init__.py` shares its module path with the package itself). Example: `--pg-config-root=/repo`, file `/repo/myapp/legacy.py` → `myapp.legacy`. File `/repo/myapp/pkg/__init__.py` → `myapp.pkg`.

**Enclosing construct.** For each `# noqa` line, walk the parent chain in the AST and find the smallest of:

- `ClassDef` (including nested) → `module.A.B`
- `FunctionDef` / `AsyncFunctionDef` → `module.A.B.method` or `module.func`
- Module scope (no enclosing function/class) → `module`

The smallest enclosing scope wins, so a `# noqa` on a method body targets `module.Class.method`, not `module.Class`. A `# noqa` on a decorator targets the decorated `FunctionDef`/method (the decorator is part of the same AST node). A `# noqa` at module top level (e.g., on a module-level assignment) targets the whole module; registry entry `fqn = "myapp.legacy"` is the matching key.

**Decorators.** Static and class methods yield the same FQN as plain methods. `@property` is preserved by the bare method name (`Class.prop`, not `Class.prop.getter`).

**Async.** `AsyncFunctionDef` follows the same rules as `FunctionDef`.

## Architecture

Single flake8 plugin (`PGPlugin` in `pydantic_guidance/flake8_guidance.py`) extended to dispatch on file type. The plugin already runs once per file; no new entry point.

```
flake8 dispatch
   ├── filename ends in .py / .pyi     → AST scan + registry lookup  → PG201–PG204
   ├── filename ends in .cfg / .toml    → config parser               → PG205
   └── filename is anything else        → no PG findings
```

### Module layout

```
pydantic_guidance/
  flake8_guidance.py        # PGPlugin (extended)
  _suppression_registry.py  # NEW: load + validate registry from pyproject.toml
  _suppression_scanner.py   # NEW: per-file AST scanner, emits PG201-PG204
  _config_scanner.py        # NEW: config-file scanner, emits PG205
  _fqn.py                   # NEW: AST → FQN resolution
  _models.py                # ADDED: SuppressionEntry model
```

The analyzer stays pure: `analyze(tree, fqn_root, registry) -> list[GuidanceFinding]`. The flake8 wrapper feeds it the right `fqn_root` and `registry` per file. No I/O inside the analyzer.

### Registry loading

`_suppression_registry.load(root: Path) -> SuppressionRegistry` reads `[tool.pydantic_guidance.suppressions]` from `<root>/pyproject.toml` once per flake8 run. Cached on the plugin instance.

The registry is loaded eagerly in `parse_options` so the scanner never blocks on disk I/O during `run()`. Missing `pyproject.toml` is not an error: the registry is empty, and every `# noqa: PGxxx` triggers `PG203`. Malformed registry entries fire `PG206` (see Future Work) on the `pyproject.toml` visit.

### FQN root resolution

`fqn_root` is the directory passed as `--pg-config-root`, defaulting to `os.getcwd()`. Used to translate filenames to dotted module paths. The existing `--pg-config-root` option is reused.

### Per-file flow

For each file flake8 visits:

1. Determine file kind by suffix.
2. If Python: parse AST. Compute FQNs for every `# noqa` line. Compare against `analyze()` output for `PG204`. Look up registry for `PG203`. Inspect comment text for `PG201`/`PG202`.
3. If config: parse with `tomllib` (TOML) or `configparser` (INI). Walk `per-file-ignores`, `extend-ignore`, and inline `# flake8:` blocks. Emit `PG205` per disabled PG/PYD code.
4. Yield findings via `RESULT_ADAPTER`.

## Error Handling

- **Missing `pyproject.toml`:** registry is empty. Every `# noqa: PGxxx` triggers `PG203`. This is the safe default: nothing is authorized until documented.
- **Malformed registry:** each malformed entry emits `PG206` against `pyproject.toml`. The scanner continues with the well-formed entries.
- **Unparseable Python file:** flake8 handles parse errors upstream; the PG plugin runs only on parseable trees.
- **Unparseable config file:** the config scanner catches `tomllib.TOMLDecodeError` / `configparser.Error` and emits one summary finding (no specific code; skipped in this iteration — see Future Work).
- **Filename outside `--pg-config-root`:** cannot derive a module path. The plugin logs once and skips `PG203`/`PG204` for that file (cannot check what it cannot name). `# noqa` on such a file still triggers `PG201`/`PG202`.

## Testing

```
tests/
  unit/
    test_fqn.py                 # FQN derivation across nesting, async, decorators
    test_registry.py            # load + validate SuppressionEntry
    test_scanner_pg201.py       # blanket # noqa
    test_scanner_pg202.py       # broad noqa
    test_scanner_pg203.py       # missing registry entry
    test_scanner_pg204.py       # stale registry entry
    test_scanner_pg205.py       # config-file disables
  features/
    suppression_scanner.feature # end-to-end: build a sample project, run flake8, observe findings
```

Tests live outside `pydantic_guidance/`, per the repo layout rule. The `tests/` directory does not currently exist in the worktree; it is created as part of this feature.

Pre-commit gains a `make test` invocation, gated by the existing `Makefile`. `make test-unit` runs the unit suite; `make features-test` runs the BDD suite (already declared but not wired).

## Documentation Updates

- `README.md`: add a "Suppression Scanner" section under the existing "Suppression" heading, documenting `PG201`–`PG205`, the registry format, and the HITL workflow.
- `docs/ide-setup.md`: add a note that IDEs must refresh their flake8 plugin list to pick up new PG2xx codes.
- `CHANGELOG.md`: add an entry under `[Unreleased]` describing the new codes and registry.
- `pydantic_guidance/_rules/PG2xx.md`: per-code rule docs matching the format of `PG001.md` etc.

## Pre-Existing Repo Gaps

This feature surfaces two pre-existing gaps that are out of scope to fix here but should be tracked:

1. No `AGENTS.md`, `CHANGELOG.md`, `CLAUDE.md`, `.pre-commit-config.yaml` commit-msg hook, or `tests/` directory at the repo root. The repo is below the standard layout. Tracked separately.
2. The existing `Makefile` declares `test-unit`, `test`, `typecheck`, `fix`, `check`, `bump`, `clean` but no `features-test` target. The behaviour suite path is referenced but not built. Tracked separately.

## Future Work

- **`PG206` — malformed registry entry.** Out of scope for this iteration; logged as a follow-up so the initial release ships with a clean error surface.
- **`pg-scan` standalone CLI.** Re-use the scanner module for ad-hoc audits (e.g., quarterly suppression review). The architecture allows this without rework.
- **Aggregate dashboard.** "Top 10 suppressed constructs across the org" requires cross-repo aggregation; out of scope.
- **Auto-link registry entries to PRs.** `approved_sha` is a starting point; GitHub PR linking is a future enhancement.

## Open Questions

None. All design decisions captured.
