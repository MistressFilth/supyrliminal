# IDE Setup Guide for pydantic-guidance

`pydantic-guidance` provides one first-party flake8 checker plugin:

- **PG** (`PGPlugin`) — pydantic-guidance hints (codes PG001–PG003
  default-on, PG101 opt-in, PG201–PG205 default-on suppression scanner)

The plugin surfaces inline diagnostics in VS Code, PyCharm, and Neovim via the
standard flake8 protocol. No additional plugin code is required beyond
installing `pydantic-guidance`.

Installing `pydantic-guidance` also pulls in the official
[`flake8-pydantic`](https://pypi.org/project/flake8-pydantic/) plugin as a
runtime dependency. Its `PYDxxx` codes appear in the same flake8 diagnostic
stream as PG and require no extra configuration; suppress individual rules
with `# noqa: PYDxxx` or via standard `extend-ignore` / `per-file-ignores`.

## Installation

```bash
pip install pydantic-guidance
# or
uv add pydantic-guidance
```

After installation, flake8 discovers the PG plugin automatically via its
`flake8.extension` entry point.

## Configuration

### Config root

The plugin resolves `pg-config-root` to locate
`.true-spec/project/true-spec.toml`. Set this option in your flake8 config file
pointing to the project root directory.

### VS Code and Neovim (ALE)

Add to `.flake8`:

```ini
[flake8]
pg-config-root = /path/to/project/root
```

### PyCharm

Add to `setup.cfg`:

```ini
[flake8]
pg-config-root = /path/to/project/root
```

## true-spec.toml Options

Configure enforcement via the `[hooks]` section of
`.true-spec/project/true-spec.toml`:

```toml
[hooks]
structured_data_enforcement = true   # set false to disable all PG checks
```

When `true-spec.toml` is absent or malformed, the plugin applies safe defaults
(gate `true`) and continues emitting diagnostics without propagating
exceptions to the flake8 host process.

PG is boundary-aware and carries no pydantic-vs-dataclass mode switch. Per-code
activation is controlled through flake8's `--select` / `--extend-select` /
`# noqa` rather than a config key. PG101 is opt-in:

```ini
[flake8]
extend-select = PG101
```

## Violation Codes

### PG (pydantic-guidance)

| Code   | Activation  | Description                                                              |
|--------|-------------|--------------------------------------------------------------------------|
| PG001  | default-on  | `TypeAdapter(...)` constructed inside a function; build once at module scope |
| PG002  | default-on  | `TypeAdapter` used as a field annotation; use `RootModel` instead         |
| PG003  | default-on  | Deprecated `@root_validator`; use `@model_validator(mode=...)`            |
| PG101  | opt-in      | `BaseModel` subclass uses no Pydantic surface; a stdlib `@dataclass` is lighter |
| PG201  | default-on  | Blanket `# noqa` with no codes listed — list specific codes or remove the line |
| PG202  | default-on  | Broad `# noqa` listing 3+ PG/PYD codes — narrow to specific constructs via the registry |
| PG203  | default-on  | `# noqa: PGxxx` / `# noqa: PYDxxx` whose construct has no matching entry in `[tool.pydantic_guidance.suppressions]` |
| PG204  | default-on  | Registry entry whose target construct no longer triggers the listed code (stale) |
| PG205  | default-on  | Project settings (`per-file-ignores`, `extend-ignore`, inline `# flake8:`) disable a PG/PYD code |

For the upstream `PYDxxx` rule catalog, see
[flake8-pydantic on PyPI](https://pypi.org/project/flake8-pydantic/).

## IDE-Specific Setup

### VS Code

1. Install the [ms-python.flake8](https://marketplace.visualstudio.com/items?itemName=ms-python.flake8) extension.
2. Configure the extension to use your project's virtual environment.
3. Add `pg-config-root` to `.flake8` as shown above.
4. PG diagnostics appear inline as you edit.

### PyCharm

1. Enable flake8 under **Settings > Tools > External Tools** or via the
   **Python > Flake8** inspection, pointing to the project venv's flake8 binary.
2. Add `pg-config-root` to `setup.cfg` under `[flake8]`.
3. PG codes surface as inspections.

### Neovim (ALE)

1. Install [ALE](https://github.com/dense-analysis/ale) and configure it to use
   flake8 as a Python linter.
2. Add `pg-config-root` to `.flake8`.
3. PG codes appear in ALE's diagnostics list on file save.

## Refreshing the IDE plugin list

When you upgrade `pydantic-guidance` to a version that adds new codes (e.g.,
the `PG2xx` suppression scanner series), your IDE must refresh its flake8
plugin list before the new codes appear inline. The flake8 binary itself
picks up new codes automatically on next invocation, but IDE linter caches do
not.

- **VS Code (ms-python.flake8):** run the `Flake8: Reset Counts` command, or
  reload the window (`Developer: Reload Window`) to force the language server
  to re-enumerate flake8 codes.
- **PyCharm:** invalidate caches via `File > Invalidate Caches...`, then
  re-trigger the flake8 inspection.
- **Neovim (ALE):** restart ALE (`:ALEStop` then `:ALERestart`) or the entire
  editor to drop the cached code list.

Until the IDE reloads, existing `PG2xx` findings will still surface from the
CLI but may not appear as inline diagnostics.
