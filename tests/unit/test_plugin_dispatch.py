from __future__ import annotations

import ast
from pathlib import Path

from pydantic_guidance._models import SuppressionRegistry
from pydantic_guidance.flake8_guidance import PGPlugin


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


def test_run_python_handles_latin1_source(tmp_path: Path) -> None:
    """flake8 reads latin-1 source via tokenize.open; the plugin must too.

    `UnicodeDecodeError` is a `ValueError`, not an `OSError`, so a plain
    `except OSError` guard turns every latin-1 file into E999. The
    plugin must fall back to latin-1 when UTF-8 fails.
    """
    p = tmp_path / "legacy.py"
    p.write_bytes("# coding: latin-1\nx = 'caf\xe9'  # noqa\n".encode("latin-1"))
    src = p.read_text(encoding="latin-1")
    plugin = PGPlugin(ast.parse(src), str(p))
    PGPlugin._project_root = str(tmp_path)  # type: ignore[attr-defined]
    findings = list(plugin._run_python())
    assert all(f.code != "E999" for f in findings)
    assert any(f.code == "PG201" for f in findings)
