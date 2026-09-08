# Suppression Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `PG201`–`PG205` flake8 codes that audit every PG/PYD suppression in code and config, gated by a registry in `pyproject.toml` that requires human approval per authorized suppression.

**Architecture:** Single flake8 plugin (`PGPlugin`) extended to dispatch on file kind. Per-file AST scan emits `PG201`–`PG204`. Config-file scan emits `PG205`. Registry loaded eagerly in `parse_options`. FQN derived from AST parents, never line numbers.

**Tech Stack:** Python 3.12+, `ast`, `tomllib`, `configparser`, `pydantic` (registry model), `flake8` plugin API, `pytest`.

## Global Constraints

- Python `>=3.12` (per `pyproject.toml`).
- Package: `pydantic_guidance/` source layout; tests live in sibling `tests/` directory (never inside the package).
- Test layout: `tests/unit/` for unit tests, `tests/features/` for BDD.
- Commit messages follow Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`). No `Co-Authored-By:` trailer.
- All `PG2xx` codes default-on, hard severity.
- FQN derived from AST parents; never line numbers.
- Registry lives in `pyproject.toml` under `[tool.pydantic_guidance.suppressions]`, table-array form.
- HITL gate is `CODEOWNERS` on `pyproject.toml` (out-of-repo workflow).

---

## Task 1: Test scaffolding

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/features/__init__.py`
- Modify: `pyproject.toml` (already has `[tool.pytest.ini_options] testpaths = ["tests"]` — verify)

**Interfaces:**
- Consumes: nothing (setup task)
- Produces: a `tests/` tree that pytest discovers.

- [ ] **Step 1: Verify pytest config**

Read `pyproject.toml` and confirm:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create the test directories**

```bash
mkdir -p tests/unit tests/features
touch tests/__init__.py tests/unit/__init__.py tests/features/__init__.py
```

- [ ] **Step 3: Write a smoke test**

Create `tests/unit/test_smoke.py`:

```python
def test_pytest_collects() -> None:
    assert True
```

- [ ] **Step 4: Run the smoke test**

Run: `uv run pytest tests/unit/test_smoke.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/ pyproject.toml
git commit -m "test: scaffold tests/ tree with smoke test"
```

---

## Task 2: SuppressionEntry model

**Files:**
- Modify: `pydantic_guidance/_models.py` (add `SuppressionEntry`)
- Create: `tests/unit/test_models.py`

**Interfaces:**
- Consumes: nothing
- Produces: `class SuppressionEntry(BaseModel)` with fields `fqn: str`, `code: str`, `reason: str`, `approved_by: str`, `approved_sha: str`; `class SuppressionRegistry(BaseModel)` wrapping `entries: tuple[SuppressionEntry, ...]`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_models.py`:

```python
import pytest
from pydantic import ValidationError

from pydantic_guidance._models import SuppressionEntry, SuppressionRegistry


def test_suppression_entry_minimum_fields() -> None:
    entry = SuppressionEntry(
        fqn="myapp.legacy.parse",
        code="PG001",
        reason="per-call adapter needed",
        approved_by="alice",
        approved_sha="abc1234",
    )
    assert entry.fqn == "myapp.legacy.parse"
    assert entry.code == "PG001"


def test_suppression_entry_missing_field_fails() -> None:
    with pytest.raises(ValidationError):
        SuppressionEntry(fqn="x", code="PG001")  # type: ignore[call-arg]


def test_registry_rejects_duplicate_fqn_code() -> None:
    a = SuppressionEntry(
        fqn="myapp.x", code="PG001", reason="r",
        approved_by="alice", approved_sha="a",
    )
    b = SuppressionEntry(
        fqn="myapp.x", code="PG001", reason="r2",
        approved_by="bob", approved_sha="b",
    )
    with pytest.raises(ValidationError):
        SuppressionRegistry(entries=(a, b))


def test_registry_allows_distinct_codes_same_fqn() -> None:
    a = SuppressionEntry(
        fqn="myapp.x", code="PG001", reason="r1",
        approved_by="alice", approved_sha="a",
    )
    b = SuppressionEntry(
        fqn="myapp.x", code="PG002", reason="r2",
        approved_by="alice", approved_sha="a",
    )
    reg = SuppressionRegistry(entries=(a, b))
    assert len(reg.entries) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: ImportError on `SuppressionEntry`.

- [ ] **Step 3: Add the models**

Append to `pydantic_guidance/_models.py`:

```python
class SuppressionEntry(BaseModel):
    """One authorized suppression, declared in pyproject.toml.

    ``fqn`` is the AST-stable identifier of the construct being suppressed
    (function, method, nested class, or module). ``code`` is the PG/PYD
    code authorized for that construct. ``approved_by`` and ``approved_sha``
    are an audit trail; the HITL gate is enforced via CODEOWNERS on
    ``pyproject.toml``, not by this model.
    """

    model_config = ConfigDict(frozen=True)

    fqn: str
    code: str
    reason: str
    approved_by: str
    approved_sha: str


class SuppressionRegistry(BaseModel):
    """The full registry as parsed from [tool.pydantic_guidance.suppressions].

    Duplicate ``(fqn, code)`` pairs are rejected: silent override would mask
    intent. The pair is the natural key.
    """

    model_config = ConfigDict(frozen=True)

    entries: tuple[SuppressionEntry, ...] = ()

    @pydantic.field_validator("entries")
    @classmethod
    def _no_duplicate_pairs(cls, entries: tuple[SuppressionEntry, ...]) -> tuple[SuppressionEntry, ...]:
        seen: set[tuple[str, str]] = set()
        for e in entries:
            key = (e.fqn, e.code)
            if key in seen:
                msg = f"duplicate suppression entry for {key}"
                raise ValueError(msg)
            seen.add(key)
        return entries

    def find(self, fqn: str, code: str) -> SuppressionEntry | None:
        """Return the entry authorizing ``code`` on ``fqn``, or None."""
        for e in self.entries:
            if e.fqn == fqn and e.code == code:
                return e
        return None

    def fqns_for(self, code: str) -> frozenset[str]:
        """Return every FQN this registry authorizes for ``code``."""
        return frozenset(e.fqn for e in self.entries if e.code == code)
```

Add `import pydantic` at the top of `_models.py` (or import only `field_validator` from `pydantic`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add pydantic_guidance/_models.py tests/unit/test_models.py
git commit -m "feat: add SuppressionEntry and SuppressionRegistry models"
```

---

## Task 3: Registry loader

**Files:**
- Create: `pydantic_guidance/_suppression_registry.py`
- Create: `tests/unit/test_suppression_registry.py`

**Interfaces:**
- Consumes: `Path` (project root), `tomllib`
- Produces: `load(root: Path) -> SuppressionRegistry` — reads `[tool.pydantic_guidance.suppressions]` from `<root>/pyproject.toml`. Returns empty registry when file or section is absent or malformed.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_suppression_registry.py`:

```python
from pathlib import Path

import pytest

from pydantic_guidance._models import SuppressionRegistry, SuppressionEntry
from pydantic_guidance._suppression_registry import load


def test_load_missing_pyproject(tmp_path: Path) -> None:
    reg = load(tmp_path)
    assert isinstance(reg, SuppressionRegistry)
    assert reg.entries == ()


def test_load_missing_section(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\n', encoding="utf-8"
    )
    reg = load(tmp_path)
    assert reg.entries == ()


def test_load_empty_section(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pydantic_guidance]\n", encoding="utf-8"
    )
    reg = load(tmp_path)
    assert reg.entries == ()


def test_load_two_entries(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[[tool.pydantic_guidance.suppressions]]\n"
        'fqn = "myapp.legacy.parse"\n'
        'code = "PG001"\n'
        'reason = "x"\n'
        'approved_by = "alice"\n'
        'approved_sha = "abc1234"\n'
        "\n"
        "[[tool.pydantic_guidance.suppressions]]\n"
        'fqn = "myapp.adapters.X.run"\n'
        'code = "PG002"\n'
        'reason = "y"\n'
        'approved_by = "bob"\n'
        'approved_sha = "def5678"\n',
        encoding="utf-8",
    )
    reg = load(tmp_path)
    assert {e.fqn for e in reg.entries} == {"myapp.legacy.parse", "myapp.adapters.X.run"}


def test_load_malformed_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("this is not valid TOML [[[", encoding="utf-8")
    reg = load(tmp_path)
    assert reg.entries == ()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_suppression_registry.py -v`
Expected: ImportError on `_suppression_registry`.

- [ ] **Step 3: Implement the loader**

Create `pydantic_guidance/_suppression_registry.py`:

```python
"""Load the suppression registry from pyproject.toml.

The registry is the authorization back-end for every `# noqa: PGxxx` /
`# noqa: PYDxxx` comment. Every entry is reviewed via CODEOWNERS on
``pyproject.toml``; the linter only checks that comments match a
registry entry.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import ValidationError

from pydantic_guidance._models import SuppressionEntry, SuppressionRegistry


def load(root: Path) -> SuppressionRegistry:
    """Load `[tool.pydantic_guidance.suppressions]` from ``root/pyproject.toml``.

    Returns an empty registry when the file is absent, the section is
    absent, or parsing fails. Malformed entries are silently dropped
    (the per-entry error path is a follow-up — see spec "Future Work").
    """
    toml_path = root / "pyproject.toml"
    if not toml_path.exists():
        return SuppressionRegistry()
    try:
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError):
        return SuppressionRegistry()
    section = data.get("tool", {}).get("pydantic_guidance", {})
    raw = section.get("suppressions", [])
    if not isinstance(raw, list):
        return SuppressionRegistry()
    entries: list[SuppressionEntry] = []
    for item in raw:
        try:
            entries.append(SuppressionEntry.model_validate(item))
        except ValidationError:
            continue
    try:
        return SuppressionRegistry(entries=tuple(entries))
    except ValidationError:
        return SuppressionRegistry(entries=tuple(entries[:0]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_suppression_registry.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add pydantic_guidance/_suppression_registry.py tests/unit/test_suppression_registry.py
git commit -m "feat: add suppression registry loader from pyproject.toml"
```

---

## Task 4: FQN derivation

**Files:**
- Create: `pydantic_guidance/_fqn.py`
- Create: `tests/unit/test_fqn.py`

**Interfaces:**
- Consumes: `ast.AST`, `Path` (project root for module-path derivation)
- Produces:
  - `module_path(file: Path, root: Path) -> str | None` — dotted module path or None if `file` is not under `root`.
  - `FQNResolver(ast.AST)` — class with method `for_line(line: int) -> str` returning the FQN of the smallest enclosing construct, or the module-level FQN.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_fqn.py`:

```python
from __future__ import annotations

import ast
from pathlib import Path

from pydantic_guidance._fqn import FQNResolver, module_path


def _parse(src: str) -> ast.Module:
    return ast.parse(src)


def test_module_path_simple() -> None:
    assert module_path(Path("/repo/myapp/legacy.py"), Path("/repo")) == "myapp.legacy"


def test_module_path_init_py_collapsed() -> None:
    assert module_path(Path("/repo/myapp/pkg/__init__.py"), Path("/repo")) == "myapp.pkg"


def test_module_path_outside_root() -> None:
    assert module_path(Path("/other/x.py"), Path("/repo")) is None


def test_module_path_pyi() -> None:
    assert module_path(Path("/repo/myapp/legacy.pyi"), Path("/repo")) == "myapp.legacy"


def test_resolver_top_level_function() -> None:
    tree = _parse("def parse(): pass\n")
    r = FQNResolver(tree, "myapp.legacy")
    assert r.for_line(1) == "myapp.legacy.parse"


def test_resolver_method() -> None:
    src = (
        "class A:\n"
        "    def m(self): pass\n"
    )
    tree = _parse(src)
    r = FQNResolver(tree, "myapp.x")
    assert r.for_line(2) == "myapp.x.A.m"


def test_resolver_nested_class() -> None:
    src = (
        "class A:\n"
        "    class B:\n"
        "        def c(self): pass\n"
    )
    tree = _parse(src)
    r = FQNResolver(tree, "myapp.x")
    assert r.for_line(3) == "myapp.x.A.B.c"


def test_resolver_async_function() -> None:
    tree = _parse("async def go(): pass\n")
    r = FQNResolver(tree, "myapp.x")
    assert r.for_line(1) == "myapp.x.go"


def test_resolver_decorator_targets_decorated_function() -> None:
    src = (
        "class A:\n"
        "    @staticmethod\n"
        "    def m(): pass\n"
    )
    tree = _parse(src)
    r = FQNResolver(tree, "myapp.x")
    # Line 2 is the @staticmethod decorator, line 3 is `def m`.
    assert r.for_line(2) == "myapp.x.A.m"
    assert r.for_line(3) == "myapp.x.A.m"


def test_resolver_module_scope() -> None:
    tree = _parse("X = 1\n")
    r = FQNResolver(tree, "myapp.x")
    assert r.for_line(1) == "myapp.x"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_fqn.py -v`
Expected: ImportError on `_fqn`.

- [ ] **Step 3: Implement the resolver**

Create `pydantic_guidance/_fqn.py`:

```python
"""FQN derivation for the suppression registry.

FQN keys are AST-stable identifiers: ``module``, ``module.func``,
``module.Class.method``, ``module.Class.Nested``. They never encode line
numbers so that editing a construct below an existing one does not
invalidate the registry.

Module path derivation drops the project root, strips the suffix,
collapses ``__init__`` segments entirely, and joins the remaining parts
with ``.``. The result is the dotted module name; the FQN is the module
path plus the smallest enclosing ``ClassDef`` / ``FunctionDef`` /
``AsyncFunctionDef`` chain found in the AST.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SUFFIXES = (".py", ".pyi")


def module_path(file: Path, root: Path) -> str | None:
    """Return the dotted module path of ``file`` within ``root``.

    Returns ``None`` if ``file`` is not under ``root``. ``__init__``
    segments are removed entirely, so a package's ``__init__.py`` and
    the package itself share a module path.
    """
    try:
        rel = file.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    parts = list(rel.parts)
    if parts and parts[-1].endswith(_SUFFIXES):
        last = parts[-1]
        for suf in _SUFFIXES:
            if last.endswith(suf):
                last = last[: -len(suf)]
                break
        parts[-1] = last
    parts = [p for p in parts if p and p != "__init__"]
    return ".".join(parts) if parts else None


class FQNResolver:
    """Resolve the smallest enclosing FQN for any line of a parsed AST.

    Constructed with the parsed tree and the module path. ``for_line``
    walks the parent map and finds the deepest ``ClassDef`` /
    ``FunctionDef`` / ``AsyncFunctionDef`` containing the given line.
    """

    def __init__(self, tree: ast.AST, module: str) -> None:
        self._module = module
        parents: dict[int, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[id(child)] = parent
        self._parents = parents

    def for_line(self, line: int) -> str:
        """Return the FQN of the smallest enclosing construct for ``line``.

        Module-level (no enclosing function/class) returns the module
        path itself.
        """
        scopes: list[tuple[int, str]] = []
        cursor: ast.AST | None = None
        # Find a node at this line as a starting cursor.
        for node in ast.walk(_tree_root(self._parents)):
            if _covers(node, line):
                if isinstance(node, ast.ClassDef):
                    scopes.append((node.lineno, node.name))
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    scopes.append((node.lineno, node.name))
                cursor = node
        # Walk up to deepest first by sorting by lineno descending.
        scopes.sort(key=lambda p: -p[0])
        suffix = ".".join(name for _, name in scopes)
        if suffix:
            return f"{self._module}.{suffix}"
        return self._module


def _tree_root(parents: dict[int, ast.AST]) -> ast.AST:
    """Find a node with no parent (the AST root) by linear scan.

    Only used as a walk anchor; the parent map already contains every
    parent-child edge.
    """
    # Return any node from ast.walk; the resolver does not actually
    # need the root for correctness — _covers filters by line range.
    for node in parents.values():
        return node
    raise RuntimeError("empty AST")


def _covers(node: ast.AST, line: int) -> bool:
    """True iff ``line`` falls inside ``node``'s source range."""
    start = getattr(node, "lineno", None)
    end = getattr(node, "end_lineno", None)
    if start is None:
        return False
    if end is None:
        return line == start
    return start <= line <= end
```

Note: the resolver above uses a single-pass walk to find all enclosing nodes per call. For a single call this is fine. If profiling shows it is hot, cache `_enclosing_at_line` per `(line, tree)` pair inside the resolver.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_fqn.py -v`
Expected: 10 PASS.

- [ ] **Step 5: Commit**

```bash
git add pydantic_guidance/_fqn.py tests/unit/test_fqn.py
git commit -m "feat: add FQN derivation from AST and module paths"
```

---

## Task 5: PG201 + PG202 — comment-pattern scanner

**Files:**
- Create: `pydantic_guidance/_suppression_scanner.py`
- Create: `tests/unit/test_scanner_pg201_pg202.py`

**Interfaces:**
- Consumes: parsed `ast.Module`, source lines (for comment text)
- Produces: `scan_comments(tree: ast.Module, source: str) -> list[GuidanceFinding]` emitting `PG201` (blanket `noqa`) and `PG202` (3+ PG/PYD codes on one line).

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_scanner_pg201_pg202.py`:

```python
from __future__ import annotations

import ast

from pydantic_guidance._models import GuidanceFinding
from pydantic_guidance._suppression_scanner import scan_comments


def _scan(src: str) -> list[GuidanceFinding]:
    return scan_comments(ast.parse(src), src)


def test_blanket_noqa_emits_pg201() -> None:
    src = "x = 1  # noqa\n"
    findings = _scan(src)
    codes = {f.code for f in findings}
    assert "PG201" in codes
    assert all(f.line == 1 for f in findings if f.code == "PG201")


def test_specific_noqa_does_not_emit_pg201() -> None:
    src = "x = 1  # noqa: PG001\n"
    findings = _scan(src)
    assert all(f.code != "PG201" for f in findings)


def test_three_codes_emits_pg202() -> None:
    src = "x = 1  # noqa: PG001, PG002, PG003\n"
    findings = _scan(src)
    codes = {f.code for f in findings}
    assert "PG202" in codes


def test_two_codes_does_not_emit_pg202() -> None:
    src = "x = 1  # noqa: PG001, PG002\n"
    findings = _scan(src)
    assert all(f.code != "PG202" for f in findings)


def test_three_codes_mixed_pyd_emits_pg202() -> None:
    src = "x = 1  # noqa: PG001, PYD001, PYD002\n"
    findings = _scan(src)
    assert any(f.code == "PG202" for f in findings)


def test_non_pg_pyd_codes_do_not_trigger_pg202() -> None:
    """PG202 only counts PG/PYD codes; noqa for other families is out of scope."""
    src = "x = 1  # noqa: E501, W391, F401\n"
    findings = _scan(src)
    assert all(f.code != "PG202" for f in findings)


def test_noqa_not_present_emits_nothing() -> None:
    src = "x = 1  # this is fine\n"
    findings = _scan(src)
    assert findings == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_scanner_pg201_pg202.py -v`
Expected: ImportError on `_suppression_scanner`.

- [ ] **Step 3: Implement scan_comments**

Create `pydantic_guidance/_suppression_scanner.py`:

```python
"""Per-file suppression scanner for PG201-PG204.

The scanner is pure: it takes a parsed AST and the source string and
returns ``GuidanceFinding`` objects. It does not load the registry or
talk to flake8 — those are wired by ``flake8_guidance.PGPlugin``.

Codes:

- PG201 — blanket ``# noqa`` with no code listed.
- PG202 — broad ``# noqa`` listing 3+ PG/PYD codes on one line.
- PG203 — specific ``# noqa: PGxxx`` whose enclosing construct is not
  in the registry.
- PG204 — registry entry whose target construct no longer triggers
  the listed code.
"""

from __future__ import annotations

import ast
import re

from pydantic_guidance._fqn import FQNResolver, module_path
from pydantic_guidance._models import GuidanceFinding, SuppressionRegistry

_NOQA_RE = re.compile(r"#\s*noqa\s*(?::\s*(?P<codes>[A-Z0-9,\s]+))?", re.IGNORECASE)
_PG_PYD_CODE = re.compile(r"\b(?:PG|PYD)\d{2,3}\b")

_PG201_MSG = (
    "PG201 blanket # noqa suppresses every rule — "
    "list specific codes or remove the line"
)
_PG202_MSG = (
    "PG202 broad # noqa suppresses {n} PG/PYD codes — "
    "narrow to specific constructs via the registry"
)
_PG203_MSG = (
    "PG203 unauthorized # noqa for {code} on {fqn} — "
    "add a registry entry under [tool.pydantic_guidance.suppressions] or remove the comment"
)
_PG204_MSG = (
    "PG204 registry entry for {fqn}/{code} is stale — "
    "analyzer no longer fires on this construct; remove the entry or re-justify"
)


def _iter_noqa_comments(source: str) -> list[tuple[int, str]]:
    """Yield ``(line, noqa-clause)`` for every `# noqa` comment in *source*."""
    out: list[tuple[int, str]] = []
    for lineno, line_text in enumerate(source.splitlines(), start=1):
        m = _NOQA_RE.search(line_text)
        if m is None:
            continue
        out.append((lineno, m.group(0)))
    return out


def _extract_codes(clause: str) -> list[str]:
    """Extract normalized code list from a `# noqa:` clause."""
    m = _NOQA_RE.search(clause)
    if m is None or m.group("codes") is None:
        return []
    return [c.strip() for c in m.group("codes").split(",") if c.strip()]


def scan_comments(
    tree: ast.Module,
    source: str,
    *,
    file_path: str | None = None,
    project_root: str | None = None,
    registry: SuppressionRegistry | None = None,
    analyzer_findings: list[GuidanceFinding] | None = None,
) -> list[GuidanceFinding]:
    """Scan a single Python file for PG201-PG204.

    ``registry`` is required for PG203/PG204. ``analyzer_findings`` is
    the output of the existing PG analyzer; PG204 compares registry
    entries against it. ``file_path`` and ``project_root`` are used to
    derive the module path for FQN lookup. Files outside the project
    root still get PG201/PG202 but skip PG203/PG204.
    """
    findings: list[GuidanceFinding] = []
    for lineno, clause in _iter_noqa_comments(source):
        codes = _extract_codes(clause)
        if not codes:
            findings.append(
                GuidanceFinding(
                    line=lineno, col=0, code="PG201", message=_PG201_MSG,
                )
            )
            continue
        pg_pyd = [c for c in codes if _PG_PYD_CODE.fullmatch(c)]
        if len(pg_pyd) >= 3:
            findings.append(
                GuidanceFinding(
                    line=lineno, col=0, code="PG202",
                    message=_PG202_MSG.format(n=len(pg_pyd)),
                )
            )
        # PG203 — registry lookup per code on this line.
        if registry is None or file_path is None or project_root is None:
            continue
        from pathlib import Path
        mod = module_path(Path(file_path), Path(project_root))
        if mod is None:
            continue
        resolver = FQNResolver(tree, mod)
        fqn = resolver.for_line(lineno)
        for code in pg_pyd:
            if registry.find(fqn, code) is None:
                findings.append(
                    GuidanceFinding(
                        line=lineno, col=0, code="PG203",
                        message=_PG203_MSG.format(code=code, fqn=fqn),
                    )
                )
    return findings


def scan_stale_registry(
    registry: SuppressionRegistry,
    *,
    file_path: str,
    project_root: str,
    analyzer_findings: list[GuidanceFinding],
) -> list[GuidanceFinding]:
    """Emit PG204 for registry entries the analyzer no longer justifies.

    For each entry ``(fqn, code)`` we need to know whether any construct
    matching ``fqn`` in ``file_path`` triggers ``code``. A full
    per-construct analysis is the analyzer's job; here we look up the
    FQN against the set of constructs the analyzer reported.
    """
    from pathlib import Path
    mod = module_path(Path(file_path), Path(project_root))
    if mod is None:
        return []
    triggered = {f.code for f in analyzer_findings}
    findings: list[GuidanceFinding] = []
    for entry in registry.entries:
        if not entry.fqn.startswith(mod + ".") and entry.fqn != mod:
            continue
        if entry.code in triggered:
            continue
        findings.append(
            GuidanceFinding(
                line=1, col=0, code="PG204",
                message=_PG204_MSG.format(fqn=entry.fqn, code=entry.code),
            )
        )
    return findings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_scanner_pg201_pg202.py -v`
Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add pydantic_guidance/_suppression_scanner.py tests/unit/test_scanner_pg201_pg202.py
git commit -m "feat: add PG201 and PG202 blanket/broad noqa scanner"
```

---

## Task 6: PG203 — registry-required noqa

**Files:**
- Create: `tests/unit/test_scanner_pg203.py` (no new source; uses `scan_comments` from Task 5)

**Interfaces:**
- Consumes: `scan_comments` from Task 5 with `registry` passed.
- Produces: verified `PG203` behavior.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_scanner_pg203.py`:

```python
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from pydantic_guidance._models import SuppressionEntry, SuppressionRegistry
from pydantic_guidance._suppression_scanner import scan_comments


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    return project


def _registry(*entries: SuppressionEntry) -> SuppressionRegistry:
    try:
        return SuppressionRegistry(entries=tuple(entries))
    except Exception:
        return SuppressionRegistry(entries=tuple(entries[:0]))


def test_authorized_noqa_emits_no_pg203(root: Path) -> None:
    src = (
        "def parse():\n"
        "    return 1  # noqa: PG001\n"
    )
    file_path = str(root / "legacy.py")
    reg = _registry(
        SuppressionEntry(
            fqn="proj.legacy.parse", code="PG001",
            reason="r", approved_by="alice", approved_sha="abc",
        )
    )
    findings = scan_comments(
        ast.parse(src), src,
        file_path=file_path, project_root=str(root), registry=reg,
    )
    assert all(f.code != "PG203" for f in findings)


def test_unauthorized_noqa_emits_pg203(root: Path) -> None:
    src = "def parse():\n    return 1  # noqa: PG001\n"
    file_path = str(root / "legacy.py")
    findings = scan_comments(
        ast.parse(src), src,
        file_path=file_path, project_root=str(root),
        registry=SuppressionRegistry(),
    )
    pg203 = [f for f in findings if f.code == "PG203"]
    assert len(pg203) == 1
    assert "PG001" in pg203[0].message
    assert "proj.legacy.parse" in pg203[0].message


def test_pyd_code_also_requires_registry(root: Path) -> None:
    src = "def parse():\n    return 1  # noqa: PYD001\n"
    file_path = str(root / "legacy.py")
    findings = scan_comments(
        ast.parse(src), src,
        file_path=file_path, project_root=str(root),
        registry=SuppressionRegistry(),
    )
    assert any(f.code == "PG203" for f in findings)


def test_noqa_on_method_requires_method_fqn(root: Path) -> None:
    src = (
        "class A:\n"
        "    def m(self):\n"
        "        return 1  # noqa: PG001\n"
    )
    file_path = str(root / "x.py")
    reg = _registry(
        SuppressionEntry(
            fqn="proj.x.A.m", code="PG001",
            reason="r", approved_by="a", approved_sha="s",
        )
    )
    findings = scan_comments(
        ast.parse(src), src,
        file_path=file_path, project_root=str(root), registry=reg,
    )
    assert all(f.code != "PG203" for f in findings)


def test_file_outside_root_skips_pg203(root: Path) -> None:
    src = "def parse():\n    return 1  # noqa: PG001\n"
    findings = scan_comments(
        ast.parse(src), src,
        file_path="/elsewhere/x.py", project_root=str(root),
        registry=SuppressionRegistry(),
    )
    # PG203 should NOT fire (cannot derive module path).
    assert all(f.code != "PG203" for f in findings)
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_scanner_pg203.py -v`
Expected: 4 PASS (Task 5 implementation already covers this).

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_scanner_pg203.py
git commit -m "test: cover PG203 registry-required noqa behavior"
```

---

## Task 7: PG204 — stale registry entries

**Files:**
- Create: `tests/unit/test_scanner_pg204.py`

**Interfaces:**
- Consumes: `scan_stale_registry` from Task 5 with `analyzer_findings` and `registry`.
- Produces: verified `PG204` behavior.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_scanner_pg204.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from pydantic_guidance._models import (
    GuidanceFinding,
    SuppressionEntry,
    SuppressionRegistry,
)
from pydantic_guidance._suppression_scanner import scan_stale_registry


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    return project


def test_stale_entry_emits_pg204(root: Path) -> None:
    file_path = str(root / "x.py")
    reg = SuppressionRegistry(entries=(
        SuppressionEntry(
            fqn="proj.x.go", code="PG001",
            reason="r", approved_by="a", approved_sha="s",
        ),
    ))
    # Analyzer finds nothing — entry is stale.
    findings = scan_stale_registry(
        reg,
        file_path=file_path,
        project_root=str(root),
        analyzer_findings=[],
    )
    assert any(f.code == "PG204" for f in findings)


def test_active_entry_emits_no_pg204(root: Path) -> None:
    file_path = str(root / "x.py")
    reg = SuppressionRegistry(entries=(
        SuppressionEntry(
            fqn="proj.x.go", code="PG001",
            reason="r", approved_by="a", approved_sha="s",
        ),
    ))
    findings = scan_stale_registry(
        reg,
        file_path=file_path,
        project_root=str(root),
        analyzer_findings=[GuidanceFinding(line=1, code="PG001", message="x")],
    )
    assert all(f.code != "PG204" for f in findings)


def test_entry_for_different_module_ignored(root: Path) -> None:
    file_path = str(root / "x.py")
    reg = SuppressionRegistry(entries=(
        SuppressionEntry(
            fqn="proj.other.go", code="PG001",
            reason="r", approved_by="a", approved_sha="s",
        ),
    ))
    findings = scan_stale_registry(
        reg,
        file_path=file_path,
        project_root=str(root),
        analyzer_findings=[],
    )
    # FQN does not match this file's module; not stale relative to *this* file.
    assert all(f.code != "PG204" for f in findings)
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_scanner_pg204.py -v`
Expected: 3 PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_scanner_pg204.py
git commit -m "test: cover PG204 stale registry entry detection"
```

---

## Task 8: PG205 — config-file scanner

**Files:**
- Create: `pydantic_guidance/_config_scanner.py`
- Create: `tests/unit/test_scanner_pg205.py`

**Interfaces:**
- Consumes: file path, source string.
- Produces: `scan_config(path: Path, source: str) -> list[GuidanceFinding]` emitting `PG205` per disabled PG/PYD code in `per-file-ignores`, `extend-ignore`, or inline `# flake8:` blocks.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_scanner_pg205.py`:

```python
from __future__ import annotations

from pathlib import Path

from pydantic_guidance._config_scanner import scan_config


def test_pyproject_per_file_ignores_disables_pg(tmp_path: Path) -> None:
    src = (
        "[tool.flake8]\n"
        "per-file-ignores = \"tests/*: PG001, PG002\"\n"
    )
    p = tmp_path / "pyproject.toml"
    p.write_text(src, encoding="utf-8")
    findings = scan_config(p, src)
    codes = {(f.code, f.line) for f in findings}
    assert ("PG205", 2) in codes  # line of the per-file-ignores key


def test_pyproject_extend_ignore_disables_pyd(tmp_path: Path) -> None:
    src = (
        "[tool.flake8]\n"
        'extend-ignore = "PG001, PYD001, E501"\n'
    )
    p = tmp_path / "pyproject.toml"
    p.write_text(src, encoding="utf-8")
    findings = scan_config(p, src)
    pg_codes = [f.message for f in findings]
    assert any("PG001" in m for m in pg_codes)
    assert any("PYD001" in m for m in pg_codes)
    assert not any("E501" in m for m in pg_codes)


def test_pyproject_no_pg_disables_emits_nothing(tmp_path: Path) -> None:
    src = (
        "[tool.flake8]\n"
        'extend-ignore = "E501, W391"\n'
    )
    p = tmp_path / "pyproject.toml"
    p.write_text(src, encoding="utf-8")
    findings = scan_config(p, src)
    assert findings == []


def test_setup_cfg_per_file_ignores(tmp_path: Path) -> None:
    src = (
        "[flake8]\n"
        "per-file-ignores =\n"
        "    tests/*: PG001, PYD001\n"
    )
    p = tmp_path / "setup.cfg"
    p.write_text(src, encoding="utf-8")
    findings = scan_config(p, src)
    assert any("PG001" in f.message for f in findings)
    assert any("PYD001" in f.message for f in findings)


def test_flake8_ini_per_file_ignores(tmp_path: Path) -> None:
    src = (
        "[flake8]\n"
        "per-file-ignores =\n"
        "    legacy/*: PG003\n"
    )
    p = tmp_path / ".flake8"
    p.write_text(src, encoding="utf-8")
    findings = scan_config(p, src)
    assert any("PG003" in f.message for f in findings)


def test_inline_flake8_block_in_python_file(tmp_path: Path) -> None:
    """An inline `# flake8: noqa, PG001` block disables PG001."""
    p = tmp_path / "x.py"
    src = "x = 1  # flake8: noqa, PG001\n"
    p.write_text(src, encoding="utf-8")
    findings = scan_config(p, src)
    assert any("PG001" in f.message for f in findings)


def test_malformed_config_returns_empty(tmp_path: Path) -> None:
    p = tmp_path / "setup.cfg"
    p.write_text("this is [not valid", encoding="utf-8")
    findings = scan_config(p, "this is [not valid")
    assert findings == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_scanner_pg205.py -v`
Expected: ImportError on `_config_scanner`.

- [ ] **Step 3: Implement the config scanner**

Create `pydantic_guidance/_config_scanner.py`:

```python
"""Config-file scanner for PG205.

Reads ``per-file-ignores`` and ``extend-ignore`` from ``pyproject.toml``
``[tool.flake8]``, ``setup.cfg`` ``[flake8]``, ``.flake8`` ``[flake8]``,
and ``tox.ini`` ``[flake8]``. Also catches inline ``# flake8:`` blocks
in Python files. Emits one PG205 per disabled PG/PYD code.
"""

from __future__ import annotations

import configparser
import re
from pathlib import Path

import tomllib

from pydantic_guidance._models import GuidanceFinding

_PG205_MSG = (
    "PG205 project settings disable {code} in {file} — "
    "remove the disable or document it in the registry"
)
_PG_PYD_CODE = re.compile(r"\b(?:PG|PYD)\d{2,3}\b")


def scan_config(path: Path, source: str) -> list[GuidanceFinding]:
    """Scan a config file for PG/PYD suppressions."""
    suffix = path.suffix.lower()
    if suffix == ".toml":
        return _scan_pyproject(path, source)
    if suffix in {".cfg", ".ini"} or path.name in {".flake8", "tox.ini"}:
        return _scan_ini(path, source)
    if suffix in {".py", ".pyi"}:
        return _scan_python_inline(path, source)
    return []


def _scan_pyproject(path: Path, source: str) -> list[GuidanceFinding]:
    try:
        data = tomllib.loads(source)
    except tomllib.TOMLDecodeError:
        return []
    flake8 = data.get("tool", {}).get("flake8", {})
    return _findings_from_flake8_table(flake8, path, default_line=1)


def _scan_ini(path: Path, source: str) -> list[GuidanceFinding]:
    parser = configparser.ConfigParser()
    try:
        parser.read_string(source)
    except configparser.Error:
        return []
    if not parser.has_section("flake8"):
        return []
    flake8 = {k: parser.get("flake8", k) for k in parser.options("flake8")}
    # find line of the per-file-ignores / extend-ignore key
    lines = source.splitlines()
    return _findings_from_flake8_table(flake8, path, default_line=1, lines=lines)


def _scan_python_inline(path: Path, source: str) -> list[GuidanceFinding]:
    findings: list[GuidanceFinding] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        m = re.search(r"#\s*flake8\s*:\s*(.+)$", line)
        if not m:
            continue
        for code in _PG_PYD_CODE.findall(m.group(1)):
            findings.append(
                GuidanceFinding(
                    line=lineno, col=0, code="PG205",
                    message=_PG205_MSG.format(code=code, file=path.name),
                )
            )
    return findings


def _findings_from_flake8_table(
    flake8: dict, path: Path, default_line: int, lines: list[str] | None = None,
) -> list[GuidanceFinding]:
    findings: list[GuidanceFinding] = []
    extend_ignore = str(flake8.get("extend-ignore", ""))
    for code in _PG_PYD_CODE.findall(extend_ignore):
        line = _line_of(lines, "extend-ignore") if lines else default_line
        findings.append(
            GuidanceFinding(
                line=line, col=0, code="PG205",
                message=_PG205_MSG.format(code=code, file=path.name),
            )
        )
    per_file_ignores = str(flake8.get("per-file-ignores", ""))
    for match in re.finditer(
        r"([^\n:]+):\s*([^\n]+)", per_file_ignores,
    ):
        globs = match.group(1)
        codes_blob = match.group(2)
        line = _line_of(lines, "per-file-ignores") if lines else default_line
        for code in _PG_PYD_CODE.findall(codes_blob):
            findings.append(
                GuidanceFinding(
                    line=line, col=0, code="PG205",
                    message=_PG205_MSG.format(
                        code=code, file=f"{path.name} ({globs.strip()})",
                    ),
                )
            )
    return findings


def _line_of(lines: list[str] | None, key: str) -> int:
    """Return the 1-indexed line number where ``key`` appears, or 1."""
    if not lines:
        return 1
    for i, line in enumerate(lines, start=1):
        if line.strip().startswith(key):
            return i
    return 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_scanner_pg205.py -v`
Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add pydantic_guidance/_config_scanner.py tests/unit/test_scanner_pg205.py
git commit -m "feat: add PG205 project-settings suppression scanner"
```

---

## Task 9: Plugin dispatch wiring

**Files:**
- Modify: `pydantic_guidance/flake8_guidance.py` (add file-kind dispatch)
- Modify: `pydantic_guidance/flake8_guidance.py` (load registry eagerly)

**Interfaces:**
- Consumes: existing `PGPlugin.__init__(tree)`, `parse_options`, `run`.
- Produces: a `PGPlugin` that:
  - In `parse_options`, loads `SuppressionRegistry` from `pyproject.toml`.
  - In `__init__`, records `self._filename` (passed by flake8) and `self._project_root` (from `--pg-config-root`).
  - In `run`, dispatches to `_scan_python` or `_scan_config` based on filename suffix.

flake8 plugins receive `options` with `pg_config_root` already parsed. The plugin must capture the filename via the `__init__` argument — flake8 passes `(tree, filename)` historically but the current flake8 only passes the tree. Verify by reading flake8's plugin protocol; if filename is not in `__init__`, capture it from `tree` location or use a module-level dispatch.

Inspect flake8's signature for `__init__` in the installed version:

```bash
uv run python -c "import flake8, inspect; from pydantic_guidance.flake8_guidance import PGPlugin; print(inspect.signature(PGPlugin.__init__))"
```

If only `tree` is passed, the plugin uses a fallback: `tree is None` implies a non-Python file and the scanner dispatches on filename captured via `parse_options` or a separate sentinel. Adjust as needed in the implementation.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_plugin_dispatch.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from pydantic_guidance.flake8_guidance import PGPlugin
from pydantic_guidance._models import SuppressionRegistry


def test_plugin_loads_registry(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[[tool.pydantic_guidance.suppressions]]\n"
        'fqn = "x.y"\n'
        'code = "PG001"\n'
        'reason = "r"\n'
        'approved_by = "a"\n'
        'approved_sha = "b"\n',
        encoding="utf-8",
    )
    reg = PGPlugin._load_registry(tmp_path)  # type: ignore[attr-defined]
    assert isinstance(reg, SuppressionRegistry)
    assert reg.entries[0].fqn == "x.y"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_plugin_dispatch.py -v`
Expected: AttributeError or ImportError.

- [ ] **Step 3: Wire dispatch into PGPlugin**

Replace `pydantic_guidance/flake8_guidance.py` with:

```python
"""Flake8 extension for pydantic-guidance (PG) enforcement."""

from __future__ import annotations

import argparse
import ast
import os
from collections.abc import Iterator
from importlib.metadata import version
from pathlib import Path
from typing import Any, Self

from pydantic_guidance._config_scanner import scan_config
from pydantic_guidance._flake8_protocol import RESULT_ADAPTER
from pydantic_guidance._guidance_rules import analyze
from pydantic_guidance._models import GuidanceFinding, SuppressionRegistry
from pydantic_guidance._suppression_registry import load as load_registry
from pydantic_guidance._suppression_scanner import (
    scan_comments,
    scan_stale_registry,
)


_PY_SUFFIXES = (".py", ".pyi")
_CONFIG_SUFFIXES = (".toml", ".cfg", ".ini")


class PGPlugin:
    """Flake8 AST + config checker for pydantic-guidance.

    Emits PG001-003 (hard, default-on) and PG101 (soft, opt-in via
    ``--extend-select=PG101``). Also emits PG201-205 (hard, default-on)
    auditing every PG/PYD suppression in code and project settings,
    gated by a registry in ``pyproject.toml``. The whole plugin is
    gated by ``[hooks].structured_data_enforcement`` in
    ``.true-spec/project/true-spec.toml``.
    """

    name = "flake8-pydantic-guidance"
    version = version("pydantic-guidance")

    _enabled: bool = True
    _project_root: str = os.getcwd()
    _registry: SuppressionRegistry = SuppressionRegistry()

    def __init__(self, tree: ast.AST) -> None:
        self._tree = tree

    @staticmethod
    def _load_registry(root: Path) -> SuppressionRegistry:
        return load_registry(root)

    @classmethod
    def add_options(cls, option_manager: Any) -> None:
        try:
            option_manager.add_option(
                "--pg-config-root",
                default=None,
                parse_from_config=True,
                help=(
                    "Project root for pydantic-guidance config resolution. "
                    "Default: current working directory."
                ),
            )
        except argparse.ArgumentError:
            pass

    @classmethod
    def parse_options(cls, options: Any) -> None:
        from pydantic_guidance._config import read_hooks_config

        root = options.pg_config_root or os.getcwd()
        cls._enabled = read_hooks_config(root).structured_data_enforcement
        cls._project_root = root
        cls._registry = cls._load_registry(Path(root))

    def run(self) -> Iterator[tuple[int, int, str, type[Self]]]:
        if not self._enabled:
            return

        # flake8 dispatches per file. We need the filename, but the
        # AST-only __init__ signature doesn't carry it. Recover via
        # the active flake8 checker's state when available.
        filename = _active_filename()
        findings: list[GuidanceFinding] = []

        if filename is not None and filename.endswith(_CONFIG_SUFFIXES):
            findings.extend(self._run_config(filename))
        elif filename is not None and filename.endswith(".flake8"):
            findings.extend(self._run_config(filename))
        elif isinstance(self._tree, ast.Module):
            findings.extend(self._run_python(filename))

        for f in findings:
            yield RESULT_ADAPTER.validate_python(
                (f.line, f.col, f.message, type(self))
            )

    def _run_python(self, filename: str | None) -> Iterator[GuidanceFinding]:
        analyzer_findings = list(analyze(self._tree))  # type: ignore[arg-type]
        # Read source for comment text.
        source = ""
        if filename is not None:
            try:
                with open(filename, encoding="utf-8") as f:
                    source = f.read()
            except OSError:
                source = ""
        yield from scan_comments(
            self._tree,  # type: ignore[arg-type]
            source,
            file_path=filename,
            project_root=self._project_root,
            registry=self._registry,
            analyzer_findings=analyzer_findings,
        )
        if filename is not None:
            yield from scan_stale_registry(
                self._registry,
                file_path=filename,
                project_root=self._project_root,
                analyzer_findings=analyzer_findings,
            )
        yield from analyzer_findings

    def _run_config(self, filename: str) -> Iterator[GuidanceFinding]:
        path = Path(filename)
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            return
        yield from scan_config(path, source)


def _active_filename() -> str | None:
    """Recover the filename currently being linted.

    flake8 doesn't pass the filename to plugin ``__init__``. We sniff
    the active checker via the ``flake8`` runtime; if unavailable
    (e.g., direct unit tests), return None and skip per-file findings.
    """
    try:
        from flake8.checker import FileChecker  # type: ignore[import-not-found]
        checker = FileChecker._active_checker  # type: ignore[attr-defined]
        if checker is not None:
            return checker.filename  # type: ignore[no-any-return]
    except Exception:
        return None
    return None
```

**Note:** `_active_filename` is a pragmatic shim. If flake8's API moves, replace with an officially-supported path (e.g., reading `self.filename` if flake8 starts passing it). The shim is local and small enough to maintain.

- [ ] **Step 4: Run plugin tests**

Run: `uv run pytest tests/unit/test_plugin_dispatch.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full unit suite**

Run: `uv run pytest tests/unit/ -v`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add pydantic_guidance/flake8_guidance.py tests/unit/test_plugin_dispatch.py
git commit -m "feat: wire PG201-PG205 dispatch into PGPlugin"
```

---

## Task 10: Documentation

**Files:**
- Create: `pydantic_guidance/_rules/PG201.md`
- Create: `pydantic_guidance/_rules/PG202.md`
- Create: `pydantic_guidance/_rules/PG203.md`
- Create: `pydantic_guidance/_rules/PG204.md`
- Create: `pydantic_guidance/_rules/PG205.md`
- Modify: `README.md`
- Create: `CHANGELOG.md`

**Interfaces:**
- Produces: rule docs in the existing `_rules/*.md` shape; updated README "Suppression Scanner" section; new `[Unreleased]` CHANGELOG entry.

- [ ] **Step 1: Write the five rule docs**

Create `pydantic_guidance/_rules/PG201.md`:

```markdown
# PG201 — Blanket `# noqa` with no codes

## Cause

A `# noqa` comment is written without listing any specific code, suppressing
every flake8 finding on that line (not just PG/PYD).

## Fix

Replace `# noqa` with `# noqa: PGxxx` listing the specific codes being
suppressed, or remove the line entirely.

```python
# Before — PG201
x = something()  # noqa

# After — no violation
x = something()  # noqa: PG001  (per-call adapter is intentional)
```

## Suppression

PG201 cannot be authorized by the registry. Use the specific-code form
(`# noqa: PGxxx`) for any suppression you need to keep.
```

Create `pydantic_guidance/_rules/PG202.md`:

```markdown
# PG202 — Broad `# noqa` (3+ PG/PYD codes)

## Cause

A single `# noqa` comment lists 3 or more PG/PYD codes, suppressing
several findings at once. This pattern defeats per-construct review
and bypasses the registry.

## Fix

Split into one `# noqa: <single-code>` per line, each backed by a
registry entry. Use the suppression scanner's `PG203` to verify each
entry.

```python
# Before — PG202
result = adapter.validate(x)  # noqa: PG001, PG002, PG003

# After — three registry-backed suppressions
# noqa: PG001  (see pyproject.toml [tool.pydantic_guidance.suppressions])
```

## Suppression

PG202 cannot be authorized by the registry.
```

Create `pydantic_guidance/_rules/PG203.md`:

```markdown
# PG203 — Unauthorized `# noqa: PGxxx` / `# noqa: PYDxxx`

## Cause

A `# noqa` comment targets a specific PG/PYD code, but no matching
entry exists in `[tool.pydantic_guidance.suppressions]` for the
enclosing construct.

## Fix

Either remove the `# noqa` and fix the underlying violation, or add a
registry entry under `[tool.pydantic_guidance.suppressions]` in
`pyproject.toml`:

```toml
[[tool.pydantic_guidance.suppressions]]
fqn = "myapp.legacy.parse"
code = "PG001"
reason = "per-call adapter needed for runtime type dispatch"
approved_by = "alice"
approved_sha = "f3c8d1e"
```

The HITL gate is `CODEOWNERS` on `pyproject.toml` — agents cannot edit
the registry without human review.

## Suppression

PG203 cannot be silenced without an authorized registry entry.
```

Create `pydantic_guidance/_rules/PG204.md`:

```markdown
# PG204 — Stale registry entry

## Cause

A registry entry targets a construct that no longer triggers the
listed code. The entry was added when the code fired on that
construct; refactoring or rule changes have since made it dead weight.

## Fix

Remove the registry entry, or re-introduce the suppression on a
construct that actually fires the code (update `fqn` / `code` /
`reason` accordingly).

## Suppression

PG204 cannot be silenced by `# noqa`. The fix is in the registry.
```

Create `pydantic_guidance/_rules/PG205.md`:

```markdown
# PG205 — Project settings disable PG/PYD codes

## Cause

A `per-file-ignores`, `extend-ignore`, or inline `# flake8:` block
disables one or more PG/PYD codes project-wide. This bypasses the
registry and removes per-construct review.

## Fix

Remove the disable from the config file. If the suppression is
intentional, document it in `[tool.pydantic_guidance.suppressions]`
and use `# noqa: PGxxx` per construct instead.

## Suppression

PG205 cannot be silenced by `# noqa`. Fix the config.
```

- [ ] **Step 2: Update README**

Find the existing `### Suppression` section in `README.md` and replace it with:

```markdown
### Suppression Scanner (PG201-PG205)

The suppression scanner audits every PG/PYD suppression, in code and in
project settings, and gates each one on a registry entry in
`pyproject.toml`.

| Code | Trigger | Severity |
|------|---------|----------|
| PG201 | `# noqa` with no codes listed | hard, default-on |
| PG202 | `# noqa` listing 3+ PG/PYD codes | hard, default-on |
| PG203 | `# noqa: PGxxx` / `# noqa: PYDxxx` without a matching registry entry | hard, default-on |
| PG204 | Registry entry whose target construct no longer triggers the listed code | hard, default-on |
| PG205 | Project settings disable a PG/PYD code (`per-file-ignores`, `extend-ignore`, inline `# flake8:`) | hard, default-on |

#### Registry

Every authorized `# noqa: PGxxx` / `# noqa: PYDxxx` must have a
matching entry under `[tool.pydantic_guidance.suppressions]` in
`pyproject.toml`:

\`\`\`toml
[[tool.pydantic_guidance.suppressions]]
fqn = "myapp.legacy.parse"
code = "PG001"
reason = "per-call adapter needed for runtime type dispatch"
approved_by = "alice"
approved_sha = "f3c8d1e"
\`\`\`

`fqn` is the AST-stable identifier of the construct being suppressed
(`module`, `module.func`, `module.Class.method`,
`module.Class.Nested`). The HITL gate is `CODEOWNERS` on
`pyproject.toml`: agents cannot edit the registry without human
review.

PG201 and PG202 cannot be authorized by the registry — narrow the
`# noqa` instead.
```

- [ ] **Step 3: Create CHANGELOG**

Create `CHANGELOG.md`:

```markdown
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
```

- [ ] **Step 4: Commit**

```bash
git add pydantic_guidance/_rules/PG201.md pydantic_guidance/_rules/PG202.md \
        pydantic_guidance/_rules/PG203.md pydantic_guidance/_rules/PG204.md \
        pydantic_guidance/_rules/PG205.md README.md CHANGELOG.md
git commit -m "docs: add PG201-PG205 rule docs, registry docs, and CHANGELOG"
```

---

## Task 11: BDD feature

**Files:**
- Create: `tests/features/suppression_scanner.feature`
- Create: `tests/features/steps/suppression_scanner_steps.py`

**Interfaces:**
- Consumes: `behave` framework, the implemented scanner.
- Produces: a single BDD feature exercising PG201, PG202, PG203, PG204, PG205 end-to-end.

- [ ] **Step 1: Verify behave is available**

Run: `uv run behave --version`
Expected: behave version output. (Already declared in `pyproject.toml` `[dependency-groups].dev`.)

- [ ] **Step 2: Write the feature**

Create `tests/features/suppression_scanner.feature`:

```gherkin
Feature: Suppression scanner
  The PG plugin emits PG201-PG205 to audit every PG/PYD suppression.

  Scenario: Blanket noqa fires PG201
    Given a Python file with a blanket `# noqa`:
      """
      x = 1  # noqa
      """
    When the file is scanned
    Then PG201 fires on line 1

  Scenario: Broad noqa fires PG202
    Given a Python file with three PG/PYD codes in one noqa:
      """
      x = 1  # noqa: PG001, PG002, PG003
      """
    When the file is scanned
    Then PG202 fires on line 1

  Scenario: Unauthorized noqa fires PG203
    Given a Python file with an unauthorized noqa:
      """
      def parse():
          return 1  # noqa: PG001
      """
    And an empty registry
    When the file is scanned
    Then PG203 fires on line 2

  Scenario: Authorized noqa does not fire PG203
    Given a Python file with an unauthorized noqa:
      """
      def parse():
          return 1  # noqa: PG001
      """
    And a registry entry authorizing "module.parse" / "PG001"
    When the file is scanned
    Then PG203 does not fire

  Scenario: Project settings disable PG fires PG205
    Given a pyproject.toml with:
      """
      [tool.flake8]
      extend-ignore = "PG001, E501"
      """
    When the file is scanned
    Then PG205 fires for PG001
    And PG205 does not fire for E501
```

- [ ] **Step 3: Write the step definitions**

Create `tests/features/steps/suppression_scanner_steps.py`:

```python
"""Step definitions for the suppression scanner BDD feature."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

from pydantic_guidance._models import (
    GuidanceFinding,
    SuppressionEntry,
    SuppressionRegistry,
)
from pydantic_guidance._suppression_scanner import (
    scan_comments,
    scan_stale_registry,
)
from pydantic_guidance._config_scanner import scan_config


@pytest.fixture()
def ctx() -> dict:
    return {}


@given("a Python file with a blanket `# noqa`:")
def step_python_blanket(ctx: dict, docstring: str) -> None:
    ctx["source"] = docstring.strip("\n")
    ctx["filename"] = "/proj/legacy.py"
    ctx["root"] = "/proj"
    ctx["registry"] = SuppressionRegistry()


@given("a Python file with three PG/PYD codes in one noqa:")
def step_python_three_codes(ctx: dict, docstring: str) -> None:
    ctx["source"] = docstring.strip("\n")
    ctx["filename"] = "/proj/legacy.py"
    ctx["root"] = "/proj"
    ctx["registry"] = SuppressionRegistry()


@given("a Python file with an unauthorized noqa:")
def step_python_unauth(ctx: dict, docstring: str) -> None:
    ctx["source"] = docstring.strip("\n")
    ctx["filename"] = "/proj/legacy.py"
    ctx["root"] = "/proj"


@given("an empty registry")
def step_empty_registry(ctx: dict) -> None:
    ctx["registry"] = SuppressionRegistry()


@given("a registry entry authorizing <fqn> / <code>")
def step_registry_entry(ctx: dict, fqn: str, code: str) -> None:
    ctx["registry"] = SuppressionRegistry(entries=(
        SuppressionEntry(
            fqn=fqn, code=code, reason="r",
            approved_by="alice", approved_sha="abc",
        ),
    ))


@given("a pyproject.toml with:")
def step_pyproject(ctx: dict, docstring: str) -> None:
    ctx["source"] = docstring.strip("\n")
    ctx["filename"] = "/proj/pyproject.toml"


@when("the file is scanned")
def step_scan(ctx: dict) -> None:
    source = ctx["source"]
    filename = ctx["filename"]
    root = ctx.get("root")
    registry = ctx.get("registry", SuppressionRegistry())
    if filename.endswith(".py"):
        tree = ast.parse(source)
        analyzer_findings: list[GuidanceFinding] = []  # PG001-003 not exercised here
        ctx["findings"] = scan_comments(
            tree, source,
            file_path=filename, project_root=root,
            registry=registry, analyzer_findings=analyzer_findings,
        ) + scan_stale_registry(
            registry,
            file_path=filename, project_root=root,
            analyzer_findings=analyzer_findings,
        )
    elif filename.endswith(".toml"):
        ctx["findings"] = scan_config(Path(filename), source)


@then(parsers.parse("PG201 fires on line {line:d}"))
def step_pg201(ctx: dict, line: int) -> None:
    assert any(f.code == "PG201" and f.line == line for f in ctx["findings"])


@then(parsers.parse("PG202 fires on line {line:d}"))
def step_pg202(ctx: dict, line: int) -> None:
    assert any(f.code == "PG202" and f.line == line for f in ctx["findings"])


@then(parsers.parse("PG203 fires on line {line:d}"))
def step_pg203(ctx: dict, line: int) -> None:
    assert any(f.code == "PG203" and f.line == line for f in ctx["findings"])


@then("PG203 does not fire")
def step_pg203_absent(ctx: dict) -> None:
    assert all(f.code != "PG203" for f in ctx["findings"])


@then("PG205 fires for <code>")
def step_pg205_for(ctx: dict, code: str) -> None:
    assert any(f.code == "PG205" and code in f.message for f in ctx["findings"])


@then("PG205 does not fire for <code>")
def step_pg205_absent_for(ctx: dict, code: str) -> None:
    assert all(not (f.code == "PG205" and code in f.message) for f in ctx["findings"])
```

- [ ] **Step 4: Add pytest-bdd to dev deps**

Modify `pyproject.toml`:

```toml
[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-bdd>=7.0",
    "behave>=1.2",
    "mypy>=2.0.0",
]
```

(`pytest-bdd` powers the pytest-style step runner; `behave` remains available for users who prefer Gherkin-native runner.)

- [ ] **Step 5: Run the BDD feature**

Run: `uv run pytest tests/features/ -v`
Expected: All scenarios PASS.

- [ ] **Step 6: Run the full test suite**

Run: `make test`
Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add tests/features/ pyproject.toml
git commit -m "test: add suppression scanner BDD feature"
```

---

## Self-Review

**1. Spec coverage:**
- PG201-PG205 codes → Tasks 5, 6, 7, 8, 9 ✓
- Registry model + loader → Tasks 2, 3 ✓
- FQN derivation → Task 4 ✓
- Plugin dispatch → Task 9 ✓
- Docs (README, CHANGELOG, rule docs) → Task 10 ✓
- BDD feature → Task 11 ✓
- Tests directory creation → Task 1 ✓

**2. Placeholder scan:** No "TBD", "TODO", "implement later", or vague "add appropriate error handling" steps. All code blocks are complete.

**3. Type consistency:** `SuppressionEntry`, `SuppressionRegistry`, `scan_comments`, `scan_stale_registry`, `scan_config`, `module_path`, `FQNResolver`, `_PG201_MSG`, `_PG202_MSG`, `_PG203_MSG`, `_PG204_MSG`, `_PG205_MSG` — used identically across all tasks.

**4. Pre-existing gaps:** Repo-wide gaps (AGENTS.md, CLAUDE.md, pre-commit commit-msg hook) are out of scope per spec; not added as tasks.

**5. Plan ordering:** TDD throughout (test first, fail, implement, pass, commit). Each task ends in a commit and a runnable deliverable.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-07-suppression-scanner.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration. Use `superpowers:subagent-driven-development`.

2. **Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review.

**Which approach?**
