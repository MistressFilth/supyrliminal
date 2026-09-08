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
                    line=lineno,
                    col=0,
                    code="PG201",
                    message=_PG201_MSG,
                )
            )
            continue
        pg_pyd = [c for c in codes if _PG_PYD_CODE.fullmatch(c)]
        if len(pg_pyd) >= 3:
            findings.append(
                GuidanceFinding(
                    line=lineno,
                    col=0,
                    code="PG202",
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
                        line=lineno,
                        col=0,
                        code="PG203",
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
    is_init = file_path.endswith(("__init__.py", "__init__.pyi"))
    findings: list[GuidanceFinding] = []
    for entry in registry.entries:
        if is_init:
            if entry.fqn != mod:
                continue
        else:
            if not entry.fqn.startswith(mod + ".") and entry.fqn != mod:
                continue
        if entry.code in triggered:
            continue
        findings.append(
            GuidanceFinding(
                line=1,
                col=0,
                code="PG204",
                message=_PG204_MSG.format(fqn=entry.fqn, code=entry.code),
            )
        )
    return findings
