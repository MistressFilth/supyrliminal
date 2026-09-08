from pathlib import Path

from supyrliminal._models import SuppressionRegistry
from supyrliminal._suppression_registry import load


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
    (tmp_path / "pyproject.toml").write_text("[tool.supyrliminal]\n", encoding="utf-8")
    reg = load(tmp_path)
    assert reg.entries == ()


def test_load_two_entries(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[[tool.supyrliminal.suppressions]]\n"
        'fqn = "myapp.legacy.parse"\n'
        'code = "SL001"\n'
        'reason = "x"\n'
        "\n"
        "[[tool.supyrliminal.suppressions]]\n"
        'fqn = "myapp.adapters.X.run"\n'
        'code = "SL002"\n'
        'reason = "y"\n',
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


def test_load_keeps_valid_when_one_duplicate_exists(tmp_path: Path, capsys) -> None:
    """A single duplicate pair must NOT wipe the rest of the registry.

    Pre-fix behavior: the outer ``except ValidationError`` returned an
    empty tuple, dropping every well-formed entry and producing a
    project-wide SL203 false-positive storm.
    """
    (tmp_path / "pyproject.toml").write_text(
        "[[tool.supyrliminal.suppressions]]\n"
        'fqn = "myapp.legacy.parse"\n'
        'code = "SL001"\n'
        'reason = "x"\n'
        "\n"
        "[[tool.supyrliminal.suppressions]]\n"
        'fqn = "myapp.legacy.parse"\n'
        'code = "SL001"\n'
        'reason = "duplicate"\n'
        "\n"
        "[[tool.supyrliminal.suppressions]]\n"
        'fqn = "myapp.adapters.X.run"\n'
        'code = "SL002"\n'
        'reason = "y"\n',
        encoding="utf-8",
    )
    reg = load(tmp_path)
    assert {e.fqn for e in reg.entries} == {
        "myapp.legacy.parse",
        "myapp.adapters.X.run",
    }
    err = capsys.readouterr().err
    assert "duplicate" in err.lower()
