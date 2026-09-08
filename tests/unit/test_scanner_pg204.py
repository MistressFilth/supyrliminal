from __future__ import annotations

from pathlib import Path

import pytest

from pydantic_guidance._models import (
    GuidanceFinding,
    SuppressionEntry,
    SuppressionRegistry,
)
from pydantic_guidance._suppression_scanner import scan_stale_registry


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    (tmp_path / "proj").mkdir()
    return tmp_path


def test_stale_entry_emits_pg204(root: Path) -> None:
    file_path = str(root / "proj" / "x.py")
    reg = SuppressionRegistry(
        entries=(
            SuppressionEntry(
                fqn="proj.x.go",
                code="PG001",
                reason="r",
                approved_by="a",
                approved_sha="s",
            ),
        )
    )
    # Analyzer finds nothing — entry is stale.
    findings = scan_stale_registry(
        reg,
        file_path=file_path,
        project_root=str(root),
        analyzer_findings=[],
    )
    assert any(f.code == "PG204" for f in findings)


def test_active_entry_emits_no_pg204(root: Path) -> None:
    file_path = str(root / "proj" / "x.py")
    reg = SuppressionRegistry(
        entries=(
            SuppressionEntry(
                fqn="proj.x.go",
                code="PG001",
                reason="r",
                approved_by="a",
                approved_sha="s",
            ),
        )
    )
    findings = scan_stale_registry(
        reg,
        file_path=file_path,
        project_root=str(root),
        analyzer_findings=[GuidanceFinding(line=1, code="PG001", message="x")],
    )
    assert all(f.code != "PG204" for f in findings)


def test_entry_for_different_module_ignored(root: Path) -> None:
    file_path = str(root / "proj" / "x.py")
    reg = SuppressionRegistry(
        entries=(
            SuppressionEntry(
                fqn="proj.other.go",
                code="PG001",
                reason="r",
                approved_by="a",
                approved_sha="s",
            ),
        )
    )
    findings = scan_stale_registry(
        reg,
        file_path=file_path,
        project_root=str(root),
        analyzer_findings=[],
    )
    # FQN does not match this file's module; not stale relative to *this* file.
    assert all(f.code != "PG204" for f in findings)


def test_init_py_does_not_match_submodule_entries(root: Path) -> None:
    """A package __init__.py must not report stale entries from its submodules.

    Pre-fix behavior: ``module_path`` collapses ``pkg/__init__.py`` to
    ``mod = "pkg"``. The filter then matched every entry in any
    submodule of ``pkg`` and reported them at line 1 of ``__init__.py``.
    """
    pkg = root / "pkg"
    pkg.mkdir()
    (pkg / "submodule").mkdir()
    file_path = str(pkg / "__init__.py")
    reg = SuppressionRegistry(
        entries=(
            SuppressionEntry(
                fqn="pkg.submodule.x",
                code="PG001",
                reason="r",
                approved_by="a",
                approved_sha="s",
            ),
        )
    )
    findings = scan_stale_registry(
        reg,
        file_path=file_path,
        project_root=str(root),
        analyzer_findings=[],
    )
    assert all(f.code != "PG204" for f in findings)
