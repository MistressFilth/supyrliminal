from pathlib import Path

from pydantic_guidance._models import SuppressionRegistry
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
    assert {e.fqn for e in reg.entries} == {
        "myapp.legacy.parse",
        "myapp.adapters.X.run",
    }


def test_load_malformed_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "this is not valid TOML [[[", encoding="utf-8"
    )
    reg = load(tmp_path)
    assert reg.entries == ()
