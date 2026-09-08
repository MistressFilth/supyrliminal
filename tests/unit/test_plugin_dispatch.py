from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from pydantic_guidance._models import SuppressionRegistry
from pydantic_guidance.flake8_guidance import PGPlugin


def _run_flake8(path: Path, *args: str) -> str:
    """Invoke the installed flake8 binary against ``path``. Returns stdout."""
    result = subprocess.run(
        [sys.executable, "-m", "flake8", "--select=PG,PYD", str(path), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


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


def test_flake8_dispatch_emits_pg001(tmp_path: Path) -> None:
    """End-to-end: PG001 fires when flake8 drives the plugin against real source.

    PG001 emits on a line that has no ``# noqa``, so flake8's inline
    noqa filter does not suppress it. This proves the plugin is
    instantiated by flake8's ``FileChecker.run_ast_checks`` and that
    ``filename`` reaches ``__init__`` (per the documented flake8 plugin
    protocol).

    Note: PG201/PG203 emissions on the ``# noqa`` line itself are
    suppressed by flake8's ``Violation.is_inline_ignored`` filter,
    which strips findings whose code starts with a prefix in the
    noqa's code list (``PG203``.startswith(``PG001``) is True). Direct
    plugin-invocation tests in ``test_scanner_pg20x`` cover those
    findings without the filter in the way.
    """
    src = tmp_path / "app.py"
    src.write_text(
        "def go():\n"
        "    from pydantic import TypeAdapter\n"
        "    return TypeAdapter(list[int]).validate_python([])\n",
        encoding="utf-8",
    )
    out = _run_flake8(src)
    assert "PG001" in out
