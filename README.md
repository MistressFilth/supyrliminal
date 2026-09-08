# Supyrliminal

Boundary-aware Pydantic usage guidance for Python. The Supyrliminal linter
(SL) steers Pydantic code toward the documented best practices: build a
`TypeAdapter` once at module scope, keep `TypeAdapter` out of field
annotations, use `@model_validator` over the deprecated `@root_validator`, and
reserve `BaseModel` for data that earns it.

Ships as a flake8 extension with full `--select` / `--extend-select` / `# noqa` /
`per-file-ignores` support.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

### Add to a project with uv

```console
uv add supyrliminal
```

This adds `supyrliminal` to `[project.dependencies]` in your `pyproject.toml`
and installs the package (including flake8, pydantic, and the flake8 entry
point) into the project virtual environment.

For development-only usage (linting in CI but excluded from published package
dependencies):

```console
uv add --dev supyrliminal
```

This adds the dependency to `[dependency-groups] dev` instead of
`[project.dependencies]`.

### Add manually to pyproject.toml

```toml
[project]
dependencies = [
    "supyrliminal>=0.2.0",
]
```

Then run:

```console
uv sync
```

### Install from a Git source

```console
uv add "supyrliminal @ git+https://github.com/MistressFilth/supyrliminal"
```

Or in `pyproject.toml`:

```toml
[project]
dependencies = ["supyrliminal"]

[tool.uv.sources]
supyrliminal = { git = "https://github.com/MistressFilth/supyrliminal" }
```

### Use from a Makefile without installing

Run `flake8` with the SL entry point without adding `supyrliminal` to the
project virtual environment. Make the repo URL reusable so a release bump
touches one line:

```makefile
SL_REPO ?= git+https://github.com/MistressFilth/supyrliminal@v0.2.0

lint: ## Run flake8 with SL+PYD selectors sourced from the supyrliminal repo
	uvx --from "supyrliminal @ $(SL_REPO)" \
	    flake8 --select=SL,PYD --exclude='.venv,*/.venv,.claude' .
```

`uvx` builds an ephemeral venv from the `git+https://` source, installs the
package and its dependencies, runs `flake8`, then discards the venv. uv caches
the build keyed by URL, so repeat invocations reuse it without rebuilding.

The `git+https://` form clones over your authenticated git credentials, which
also works for a private repository; a public repository can switch to the
lighter `archive/refs/tags/*.tar.gz` form.

`uvx` is the Makefile analogue of pre-commit's hook install: pre-commit
creates an isolated venv, pip-installs the dependencies + the package, and
execs the entry on staged files. `uvx --from <url>` performs the same three
steps on demand. Override the version without editing the Makefile:

```console
make lint SL_REPO=git+https://github.com/MistressFilth/supyrliminal@v0.2.0
```

## Pre-commit

Add the following to `.pre-commit-config.yaml` to run the linter on every
commit:

```yaml
repos:
  - repo: https://github.com/MistressFilth/supyrliminal
    rev: v0.2.0
    hooks:
      # Supyrliminal (SL) and PYD checks together.
      - id: supyrliminal
```

Each hook installs the package from the same repo at `additional_dependencies`
install time, so no prior `uv add` or virtual environment is required.

The hook `types_or` is `[python, pyi]`. For Jupyter notebooks or `pyproject.toml`,
extend it explicitly:

```yaml
hooks:
  - id: supyrliminal
    types_or: [python, pyi, jupyter, pyproject]
```

## Flake8 Extension

Installing `supyrliminal` registers one first-party flake8 checker plugin
automatically via entry points, and pulls in the official
[`flake8-pydantic`](https://pypi.org/project/flake8-pydantic/) plugin as a
runtime dependency for additional Pydantic-specific lint coverage:

| Entry point | Plugin class | Error prefix | Checks |
|---|---|---|---|
| `SL` | `SLPlugin` | SL001–SL003 (default-on), SL101 (opt-in) | Pydantic guidance: TypeAdapter placement, deprecated validators, BaseModel surface |
| `PYD` | `flake8-pydantic` (third-party) | PYDxxx | Pydantic-specific lint (model config, validators, fields) |

Verify registration:

```console
uv run flake8 --version
```

`flake8-pydantic` and `supyrliminal` both appear in the version output when
installed correctly.

### Running

```console
# Run Supyrliminal checks only (SL first-party + PYD upstream)
uv run flake8 --select=SL,PYD .

# Include the opt-in advisory hint SL101
uv run flake8 --select=SL,PYD --extend-select=SL101 .

# Run alongside all other flake8 checks
uv run flake8 .
```

The plugin is always on once installed. Activation of individual codes is
controlled entirely through flake8's `--select` / `--extend-select` / `# noqa` /
`per-file-ignores`.

### Error Codes

SL001–SL003 are default-on (part of the standard `--select` set). SL101 is an
advisory hint, opt-in via `--extend-select=SL101`. Hard versus soft is purely
the code number; flake8 `--select` / `--extend-select` controls activation and
`# noqa: SLxxx` works per line.

| Code | Activation | Violation | Rule reference |
|------|-----------|-----------|----------------|
| SL001 | default-on | `TypeAdapter(...)` constructed inside a function — build once at module scope and reuse | [SL001.md](supyrliminal/_rules/SL001.md) |
| SL002 | default-on | `TypeAdapter` used as a field annotation — use `RootModel` for a reusable named root type | [SL002.md](supyrliminal/_rules/SL002.md) |
| SL003 | default-on | Deprecated `@root_validator` — use `@model_validator(mode='before'\|'after')` | [SL003.md](supyrliminal/_rules/SL003.md) |
| SL101 | opt-in | `BaseModel` subclass uses no Pydantic surface — a stdlib `@dataclass` is lighter for internal state | [SL101.md](supyrliminal/_rules/SL101.md) |

### Suppression Scanner (SL201-SL205)

The suppression scanner audits every SL/PYD suppression, in code and in
project settings, and gates each one on a registry entry in `pyproject.toml`.

| Code | Trigger | Emitter | Severity |
|------|---------|---------|----------|
| SL201 | `# noqa` with no codes listed | flake8 (`SLPlugin`) | hard, default-on |
| SL202 | `# noqa` listing 3+ SL/PYD codes | flake8 (`SLPlugin`) | hard, default-on |
| SL203 | `# noqa: SLxxx` / `# noqa: PYDxxx` without a matching registry entry | flake8 (`SLPlugin`) | hard, default-on |
| SL204 | Registry entry whose target construct no longer triggers the listed code | flake8 (`SLPlugin`) | hard, default-on |
| SL205 | Project settings disable an SL/PYD code (`per-file-ignores`, `extend-ignore`, inline `# flake8:`) | `supyrliminal scan-config` CLI | hard, default-on |

SL205 ships as a CLI subcommand because flake8's AST plugin protocol calls
`ast.parse()` first and never instantiates the plugin for `.toml`/`.cfg`/`.ini`
files. Run `supyrliminal scan-config` from the project root (or pass an
explicit path) to surface every SL205:

```console
supyrliminal scan-config                # walk the current tree
supyrliminal scan-config /path/to/project
```

`sl` is a shorter alias for the same entry point, so `sl scan-config` is
equivalent. Output is flake8-compatible (`path:line:col: SL205 message`).

#### Registry

Every authorized `# noqa: SLxxx` / `# noqa: PYDxxx` must have a matching entry
under `[tool.supyrliminal.suppressions]` in `pyproject.toml`:

```toml
[[tool.supyrliminal.suppressions]]
fqn = "myapp.legacy.parse"
code = "SL001"
reason = "per-call adapter needed for runtime type dispatch"
```

`fqn` is the AST-stable identifier of the construct being suppressed
(`module`, `module.func`, `module.Class.method`, `module.Class.Nested`).
`reason` is the human-facing justification; the registry itself, tracked in
version control, is the audit record.

SL201, SL202, and SL205 cannot be authorized by the registry — narrow the
`# noqa` and clean up project settings instead.

### Configuration

The plugin resolves the suppression registry relative to a project root, which
defaults to the current working directory. Override it via flake8 option:

```console
uv run flake8 --sl-config-root=/path/to/project .
```

The option is also readable from a flake8 config file as `sl-config-root`.

Supyrliminal is boundary-aware and carries no pydantic-vs-dataclass mode
switch: there is no per-rule config file. Everything is driven by flake8's own
selectors.

### IDE Setup

For VS Code (ms-python.flake8), PyCharm (flake8 inspection), and Neovim
(ALE) configuration, see [`docs/ide-setup.md`](docs/ide-setup.md).

## Development

```console
git clone https://github.com/MistressFilth/supyrliminal
cd supyrliminal
uv sync
uv run pytest -v
```
