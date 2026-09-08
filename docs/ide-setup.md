# IDE Setup Guide for Supyrliminal

`supyrliminal` provides one first-party flake8 checker plugin:

- **SL** (`SLPlugin`) — Supyrliminal hints (codes SL001–SL003
  default-on, SL101 opt-in, SL201–SL205 default-on suppression scanner)

The plugin surfaces inline diagnostics in VS Code, PyCharm, and Neovim via the
standard flake8 protocol. No additional plugin code is required beyond
installing `supyrliminal`.

Installing `supyrliminal` also pulls in the official
[`flake8-pydantic`](https://pypi.org/project/flake8-pydantic/) plugin as a
runtime dependency. Its `PYDxxx` codes appear in the same flake8 diagnostic
stream as SL and require no extra configuration; suppress individual rules
with `# noqa: PYDxxx` or via standard `extend-ignore` / `per-file-ignores`.

## Installation

```bash
pip install supyrliminal
# or
uv add supyrliminal
```

After installation, flake8 discovers the SL plugin automatically via its
`flake8.extension` entry point. The plugin is always on; there is no config
file that enables or disables it.

## Configuration

### Config root

The plugin resolves `sl-config-root` to locate the project root holding the
suppression registry in `pyproject.toml`. It defaults to the current working
directory, which is usually correct when the IDE runs flake8 from the project
root. Set the option explicitly when the IDE's working directory differs.

### VS Code and Neovim (ALE)

Add to `.flake8`:

```ini
[flake8]
sl-config-root = /path/to/project/root
```

### PyCharm

Add to `setup.cfg`:

```ini
[flake8]
sl-config-root = /path/to/project/root
```

## Per-code activation

Supyrliminal is boundary-aware and carries no pydantic-vs-dataclass mode
switch. Per-code activation is controlled through flake8's `--select` /
`--extend-select` / `# noqa` rather than a config key. SL101 is opt-in:

```ini
[flake8]
extend-select = SL101
```

## Violation Codes

### SL (Supyrliminal)

| Code   | Activation  | Description                                                              |
|--------|-------------|--------------------------------------------------------------------------|
| SL001  | default-on  | `TypeAdapter(...)` constructed inside a function; build once at module scope |
| SL002  | default-on  | `TypeAdapter` used as a field annotation; use `RootModel` instead         |
| SL003  | default-on  | Deprecated `@root_validator`; use `@model_validator(mode=...)`            |
| SL101  | opt-in      | `BaseModel` subclass uses no Pydantic surface; a stdlib `@dataclass` is lighter |
| SL201  | default-on  | Blanket `# noqa` with no codes listed — list specific codes or remove the line |
| SL202  | default-on  | Broad `# noqa` listing 3+ SL/PYD codes — narrow to specific constructs via the registry |
| SL203  | default-on  | `# noqa: SLxxx` / `# noqa: PYDxxx` whose construct has no matching entry in `[tool.supyrliminal.suppressions]` |
| SL204  | default-on  | Registry entry whose target construct no longer triggers the listed code (stale) |
| SL205  | default-on  | Project settings (`per-file-ignores`, `extend-ignore`, inline `# flake8:`) disable an SL/PYD code — emitted by the `supyrliminal scan-config` CLI, not the flake8 plugin |

For the upstream `PYDxxx` rule catalog, see
[flake8-pydantic on PyPI](https://pypi.org/project/flake8-pydantic/).

## IDE-Specific Setup

### VS Code

1. Install the [ms-python.flake8](https://marketplace.visualstudio.com/items?itemName=ms-python.flake8) extension.
2. Configure the extension to use your project's virtual environment.
3. Add `sl-config-root` to `.flake8` as shown above if the working directory
   is not the project root.
4. SL diagnostics appear inline as you edit.

### PyCharm

1. Enable flake8 under **Settings > Tools > External Tools** or via the
   **Python > Flake8** inspection, pointing to the project venv's flake8 binary.
2. Add `sl-config-root` to `setup.cfg` under `[flake8]` if needed.
3. SL codes surface as inspections.

### Neovim (ALE)

1. Install [ALE](https://github.com/dense-analysis/ale) and configure it to use
   flake8 as a Python linter.
2. Add `sl-config-root` to `.flake8` if needed.
3. SL codes appear in ALE's diagnostics list on file save.

## Refreshing the IDE plugin list

When you upgrade `supyrliminal` to a version that adds new codes (e.g., the
`SL2xx` suppression scanner series), your IDE must refresh its flake8 plugin
list before the new codes appear inline. The flake8 binary itself picks up new
codes automatically on next invocation, but IDE linter caches do not.

- **VS Code (ms-python.flake8):** run the `Flake8: Reset Counts` command, or
  reload the window (`Developer: Reload Window`) to force the language server
  to re-enumerate flake8 codes.
- **PyCharm:** invalidate caches via `File > Invalidate Caches...`, then
  re-trigger the flake8 inspection.
- **Neovim (ALE):** restart ALE (`:ALEStop` then `:ALERestart`) or the entire
  editor to drop the cached code list.

Until the IDE reloads, existing `SL2xx` findings will still surface from the
CLI but may not appear as inline diagnostics.
