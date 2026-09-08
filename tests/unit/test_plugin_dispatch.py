from __future__ import annotations

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
