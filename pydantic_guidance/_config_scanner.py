"""Config-file scanner for PG205.

Reads ``per-file-ignores`` and ``extend-ignore`` from ``pyproject.toml``
``[tool.flake8]``, ``setup.cfg`` ``[flake8]``, ``.flake8`` ``[flake8]``,
and ``tox.ini`` ``[flake8]``. Also catches inline ``# flake8:`` blocks
in Python files. Emits one PG205 per disabled PG/PYD code.
"""

from __future__ import annotations

import configparser
import re
import tomllib
from pathlib import Path

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
    lines = source.splitlines()
    return _findings_from_flake8_table(flake8, path, default_line=1, lines=lines)


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
                    line=lineno,
                    col=0,
                    code="PG205",
                    message=_PG205_MSG.format(code=code, file=path.name),
                )
            )
    return findings


def _findings_from_flake8_table(
    flake8: dict,
    path: Path,
    default_line: int,
    lines: list[str] | None = None,
) -> list[GuidanceFinding]:
    findings: list[GuidanceFinding] = []
    extend_ignore = str(flake8.get("extend-ignore", ""))
    for code in _PG_PYD_CODE.findall(extend_ignore):
        line = _line_of(lines, "extend-ignore") if lines else default_line
        findings.append(
            GuidanceFinding(
                line=line,
                col=0,
                code="PG205",
                message=_PG205_MSG.format(code=code, file=path.name),
            )
        )
    per_file_ignores = str(flake8.get("per-file-ignores", ""))
    for match in re.finditer(r"([^\n:]+):\s*([^\n]+)", per_file_ignores):
        globs = match.group(1)
        codes_blob = match.group(2)
        line = _line_of(lines, "per-file-ignores") if lines else default_line
        for code in _PG_PYD_CODE.findall(codes_blob):
            findings.append(
                GuidanceFinding(
                    line=line,
                    col=0,
                    code="PG205",
                    message=_PG205_MSG.format(
                        code=code, file=f"{path.name} ({globs.strip()})"
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
