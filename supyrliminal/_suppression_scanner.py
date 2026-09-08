"""Per-file suppression scanner for SL201-SL204.

The scanner is pure: it takes a parsed AST and the source string and
returns ``GuidanceFinding`` objects. It does not load the registry or
talk to flake8 — those are wired by ``supyrliminal.flake8_supyrliminal.SLPlugin``.

Codes:

- SL201 — blanket ``# noqa`` with no code listed.
- SL202 — broad ``# noqa`` listing 3+ SL/PYD codes on one line.
- SL203 — specific ``# noqa: SLxxx`` whose enclosing construct is not
  in the registry.
- SL204 — registry entry whose target construct no longer triggers
  the listed code.
"""

import ast
import re

from supyrliminal._fqn import FQNResolver, module_path
from supyrliminal._models import GuidanceFinding, SuppressionRegistry

_NOQA_RE = re.compile(r"#\s*noqa\s*(?::\s*(?P<codes>[A-Z0-9,\s]+))?", re.IGNORECASE)
_SL_PYD_CODE = re.compile(r"\b(?:SL|PYD)\d{2,3}\b")

_SL201_MSG = (
    "SL201 blanket # noqa suppresses every rule — "
    "list specific codes or remove the line"
)
_SL202_MSG = (
    "SL202 broad # noqa suppresses {n} SL/PYD codes — "
    "narrow to specific constructs via the registry"
)
_SL203_MSG = (
    "SL203 unauthorized # noqa for {code} on {fqn} — "
    "add a registry entry under [tool.supyrliminal.suppressions] or remove the comment"
)
_SL204_MSG = (
    "SL204 registry entry for {fqn}/{code} is stale — "
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
    """Scan a single Python file for SL201-SL203.

    ``registry`` is required for SL203: every SL/PYD code in a
    ``# noqa:`` clause must have a matching entry under
    ``[tool.supyrliminal.suppressions]`` in ``pyproject.toml``.
    ``file_path`` and ``project_root`` are used to derive the module
    path for FQN lookup. Files outside the project root still get
    SL201/SL202 but skip SL203. ``analyzer_findings`` is unused here;
    SL204 is emitted by :func:`scan_stale_registry`, which compares
    registry entries against analyzer output.
    """
    findings: list[GuidanceFinding] = []
    for lineno, clause in _iter_noqa_comments(source):
        codes = _extract_codes(clause)
        if not codes:
            findings.append(
                GuidanceFinding(
                    line=lineno,
                    col=0,
                    code="SL201",
                    message=_SL201_MSG,
                )
            )
            continue
        pg_pyd = [c for c in codes if _SL_PYD_CODE.fullmatch(c)]
        if len(pg_pyd) >= 3:
            findings.append(
                GuidanceFinding(
                    line=lineno,
                    col=0,
                    code="SL202",
                    message=_SL202_MSG.format(n=len(pg_pyd)),
                )
            )
        # SL203 — registry lookup per code on this line.
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
                        line=lineno,
                        col=0,
                        code="SL203",
                        message=_SL203_MSG.format(code=code, fqn=fqn),
                    )
                )
    return findings


def scan_stale_registry(
    registry: SuppressionRegistry,
    *,
    file_path: str,
    project_root: str,
    analyzer_findings: list[GuidanceFinding],
    tree: ast.Module | None = None,
) -> list[GuidanceFinding]:
    """Emit SL204 for registry entries the analyzer no longer justifies.

    For each entry ``(fqn, code)`` we need to know whether the construct
    matching ``fqn`` in ``file_path`` triggers ``code``. When ``tree`` is
    provided we resolve each analyzer finding to its enclosing FQN and
    compare ``(entry.fqn, entry.code)`` against that set — collapsing to a
    bare code set would let a stale entry pass because a *different*
    construct in the same file fired the same code. Without ``tree`` we
    fall back to a module-level match, attributing every finding to the
    file's module path.

    A package's ``__init__.py`` is special-cased: its module path
    collapses to the bare package, so the prefix-match used for other
    files would falsely match every entry in any submodule. For
    ``__init__.py`` we require ``entry.fqn == mod`` exactly.
    """
    from pathlib import Path

    mod = module_path(Path(file_path), Path(project_root))
    if mod is None:
        return []
    if tree is not None:
        resolver = FQNResolver(tree, mod)
        triggered: set[tuple[str, str]] = {
            (resolver.for_line(f.line), f.code) for f in analyzer_findings
        }
    else:
        triggered = {(mod, f.code) for f in analyzer_findings}
    is_init = file_path.endswith(("__init__.py", "__init__.pyi"))
    findings: list[GuidanceFinding] = []
    location_lookup = resolver if tree is not None else None
    for entry in registry.entries:
        if is_init:
            if entry.fqn != mod:
                continue
        else:
            if not entry.fqn.startswith(mod + ".") and entry.fqn != mod:
                continue
        if (entry.fqn, entry.code) in triggered:
            continue
        line, col = (1, 0)
        if location_lookup is not None:
            found = location_lookup.line_for_fqn(entry.fqn)
            if found is not None:
                line, col = found
        findings.append(
            GuidanceFinding(
                line=line,
                col=col,
                code="SL204",
                message=_SL204_MSG.format(fqn=entry.fqn, code=entry.code),
            )
        )
    return findings
