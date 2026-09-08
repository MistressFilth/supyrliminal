from __future__ import annotations

from pathlib import Path

from pydantic_guidance._config_scanner import scan_config


def test_pyproject_per_file_ignores_disables_pg(tmp_path: Path) -> None:
    src = '[tool.flake8]\nper-file-ignores = "tests/*: PG001, PG002"\n'
    p = tmp_path / "pyproject.toml"
    p.write_text(src, encoding="utf-8")
    findings = scan_config(p, src)
    codes = {(f.code, f.line) for f in findings}
    assert ("PG205", 2) in codes  # line of the per-file-ignores key


def test_pyproject_extend_ignore_disables_pyd(tmp_path: Path) -> None:
    src = '[tool.flake8]\nextend-ignore = "PG001, PYD001, E501"\n'
    p = tmp_path / "pyproject.toml"
    p.write_text(src, encoding="utf-8")
    findings = scan_config(p, src)
    pg_codes = [f.message for f in findings]
    assert any("PG001" in m for m in pg_codes)
    assert any("PYD001" in m for m in pg_codes)
    assert not any("E501" in m for m in pg_codes)


def test_pyproject_no_pg_disables_emits_nothing(tmp_path: Path) -> None:
    src = '[tool.flake8]\nextend-ignore = "E501, W391"\n'
    p = tmp_path / "pyproject.toml"
    p.write_text(src, encoding="utf-8")
    findings = scan_config(p, src)
    assert findings == []


def test_setup_cfg_per_file_ignores(tmp_path: Path) -> None:
    src = "[flake8]\nper-file-ignores =\n    tests/*: PG001, PYD001\n"
    p = tmp_path / "setup.cfg"
    p.write_text(src, encoding="utf-8")
    findings = scan_config(p, src)
    assert any("PG001" in f.message for f in findings)
    assert any("PYD001" in f.message for f in findings)


def test_flake8_ini_per_file_ignores(tmp_path: Path) -> None:
    src = "[flake8]\nper-file-ignores =\n    legacy/*: PG003\n"
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


def test_pyproject_per_file_ignores_list_form(tmp_path: Path) -> None:
    """TOML list form of per-file-ignores must attribute each code to its glob."""
    src = (
        '[tool.flake8]\n'
        'per-file-ignores = [\n'
        '  "tests/*: PG001, PG002",\n'
        '  "legacy/*: PG003",\n'
        ']\n'
    )
    p = tmp_path / "pyproject.toml"
    p.write_text(src, encoding="utf-8")
    findings = scan_config(p, src)
    pg003 = [f for f in findings if "PG003" in f.message]
    assert pg003, "PG003 from legacy/* must be detected"
    assert any("legacy/*" in f.message for f in pg003)


def test_pyproject_extend_ignore_list_form(tmp_path: Path) -> None:
    """TOML list form of extend-ignore must collect codes from every element."""
    src = '[tool.flake8]\nextend-ignore = ["PG001", "PYD001", "E501"]\n'
    p = tmp_path / "pyproject.toml"
    p.write_text(src, encoding="utf-8")
    findings = scan_config(p, src)
    codes = [f.message for f in findings]
    assert any("PG001" in m for m in codes)
    assert any("PYD001" in m for m in codes)
    assert not any("E501" in m for m in codes)