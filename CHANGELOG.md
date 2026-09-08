# Changelog

## [0.1.0] - 2026-09-08

First release under the Supyrliminal name. The distribution, the import
package, the flake8 entry point, the plugin class, and the code prefix all
move together: install `supyrliminal`, import `supyrliminal`, select `SL`,
and expect `SLPlugin` in `flake8 --version` output. Numeric code IDs are
unchanged (001-205), and the third-party `PYD` prefix is untouched.

### Added
- SL201 — flag blanket `# noqa` with no codes listed.
- SL202 — flag broad `# noqa` listing 3+ SL/PYD codes on one line.
- SL203 — flag `# noqa: SLxxx` / `# noqa: PYDxxx` without a matching
  entry under `[tool.supyrliminal.suppressions]` in `pyproject.toml`.
- SL204 — flag registry entries whose target construct no longer
  triggers the listed code.
- SL205 — flag project settings (`per-file-ignores`, `extend-ignore`,
  inline `# flake8:`) disabling SL/PYD codes.
- Suppression registry loaded eagerly from `pyproject.toml`; FQN
  derived from AST identifiers (functions, methods, nested classes,
  module scope).
- `supyrliminal` CLI umbrella with a `scan-config` subcommand for SL205
  (flake8's AST plugin protocol cannot reach `.toml`/`.cfg`/`.ini`
  files). `sl` is installed as a shorter alias for the same entry point.

### Changed
- Project, package, and code prefix renamed to `supyrliminal` / `SL`.
  The flake8 entry-point key is `SL`, the plugin class is `SLPlugin`,
  the plugin name is `flake8-supyrliminal`, and the rule docs ship as
  `SL001.md`-`SL205.md`.
- `SLPlugin` emits only the AST-scannable codes (SL001-SL003, SL101,
  SL201-SL204); SL205 moved to the `supyrliminal scan-config`
  subcommand.
- The flake8 config-root option is now `--sl-config-root`
  (`sl-config-root` in a flake8 config file).
- The suppression registry table is now
  `[[tool.supyrliminal.suppressions]]`.
- The pre-commit hook id is now `supyrliminal`, and its entry selects
  `SL,PYD`.
- `scan_config` now dispatches by recognized filename rather than
  suffix; accepts the TOML list form of `per-file-ignores` and
  `extend-ignore`.
- `scan_stale_registry` resolves analyzer findings to their enclosing
  FQN before comparing against registry entries, so SL204 fires per
  construct rather than per code.
- `scan_stale_registry` special-cases `__init__.py` to require exact
  FQN match (no submodule prefix), preventing false positives on
  package init files.

### Removed
- External config-file gating. The plugin no longer reads a project
  config file to decide whether to run, and the config reader and its
  models are gone. The plugin is always on once installed; activation
  is controlled entirely through flake8's `--select` /
  `--extend-select` / `# noqa` / `per-file-ignores`.
- The human-review gate on registry edits. The registry in
  `pyproject.toml` is version-controlled and machine-scannable, which
  is the audit record on its own.
- The two approval-tracking fields on registry entries. An entry now
  carries `fqn`, `code`, and `reason` only.
- The `pytest-bdd` feature-test suite and its dependency. `tests/unit/`
  is the whole test tree, and `make test` runs `unit-test`.

### Fixed
- `flake8-pydantic` and other dependencies installed via pre-commit no
  longer trip over an unanchored local hook definition.

### Migration
Hard cut, no deprecation aliases. In a downstream project the upgrade is
a search-and-replace:

- `PG` → `SL` in every `# noqa:` marker and every flake8 selector.
- The old suppressions table header becomes
  `[[tool.supyrliminal.suppressions]]`.
- Drop the two approval-tracking rows from every registry entry.
- The old standalone config-scan script becomes
  `supyrliminal scan-config`.
- `--pg-config-root` → `--sl-config-root`.

Nothing from the old prefix is silently honored. A leftover `PG` marker
raises SL203 (unauthorized suppression), an old suppressions table is
ignored, and a `PG`-prefixed registry entry raises SL204 (stale registry
entry).
