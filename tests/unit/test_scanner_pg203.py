from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from pydantic_guidance._models import SuppressionEntry, SuppressionRegistry
from pydantic_guidance._suppression_scanner import scan_comments


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    (tmp_path / "proj").mkdir()
    return tmp_path


def _registry(*entries: SuppressionEntry) -> SuppressionRegistry:
    try:
        return SuppressionRegistry(entries=tuple(entries))
    except ValidationError:
        return SuppressionRegistry(entries=tuple(entries[:0]))


def test_authorized_noqa_emits_no_pg203(root: Path) -> None:
    src = "def parse():\n    return 1  # noqa: PG001\n"
    file_path = str(root / "proj" / "legacy.py")
    reg = _registry(
        SuppressionEntry(
            fqn="proj.legacy.parse",
            code="PG001",
            reason="r",
            approved_by="alice",
            approved_sha="abc",
        )
    )
    findings = scan_comments(
        ast.parse(src),
        src,
        file_path=file_path,
        project_root=str(root),
        registry=reg,
    )
    assert all(f.code != "PG203" for f in findings)


def test_unauthorized_noqa_emits_pg203(root: Path) -> None:
    src = "def parse():\n    return 1  # noqa: PG001\n"
    file_path = str(root / "proj" / "legacy.py")
    findings = scan_comments(
        ast.parse(src),
        src,
        file_path=file_path,
        project_root=str(root),
        registry=SuppressionRegistry(),
    )
    pg203 = [f for f in findings if f.code == "PG203"]
    assert len(pg203) == 1
    assert "PG001" in pg203[0].message
    assert "proj.legacy.parse" in pg203[0].message


def test_pyd_code_also_requires_registry(root: Path) -> None:
    src = "def parse():\n    return 1  # noqa: PYD001\n"
    file_path = str(root / "proj" / "legacy.py")
    findings = scan_comments(
        ast.parse(src),
        src,
        file_path=file_path,
        project_root=str(root),
        registry=SuppressionRegistry(),
    )
    assert any(f.code == "PG203" for f in findings)


def test_noqa_on_method_requires_method_fqn(root: Path) -> None:
    src = "class A:\n    def m(self):\n        return 1  # noqa: PG001\n"
    file_path = str(root / "proj" / "x.py")
    reg = _registry(
        SuppressionEntry(
            fqn="proj.x.A.m",
            code="PG001",
            reason="r",
            approved_by="a",
            approved_sha="s",
        )
    )
    findings = scan_comments(
        ast.parse(src),
        src,
        file_path=file_path,
        project_root=str(root),
        registry=reg,
    )
    assert all(f.code != "PG203" for f in findings)


def test_file_outside_root_skips_pg203(root: Path) -> None:
    src = "def parse():\n    return 1  # noqa: PG001\n"
    findings = scan_comments(
        ast.parse(src),
        src,
        file_path="/elsewhere/x.py",
        project_root=str(root),
        registry=SuppressionRegistry(),
    )
    # PG203 should NOT fire (cannot derive module path).
    assert all(f.code != "PG203" for f in findings)
