import ast
from pathlib import Path

import pytest

from supyrliminal._models import (
    GuidanceFinding,
    SuppressionEntry,
    SuppressionRegistry,
)
from supyrliminal._suppression_scanner import scan_stale_registry


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    (tmp_path / "proj").mkdir()
    return tmp_path


def _tree(src: str) -> ast.Module:
    return ast.parse(src)


def test_stale_entry_emits_pg204(root: Path) -> None:
    file_path = str(root / "proj" / "x.py")
    tree = _tree("def go(): pass\n")
    reg = SuppressionRegistry(
        entries=(
            SuppressionEntry(
                fqn="proj.x.go",
                code="SL001",
                reason="r",
            ),
        )
    )
    # Analyzer finds nothing for proj.x.go — entry is stale.
    findings = scan_stale_registry(
        reg,
        file_path=file_path,
        project_root=str(root),
        analyzer_findings=[],
        tree=tree,
    )
    assert any(f.code == "SL204" for f in findings)


def test_active_entry_emits_no_pg204(root: Path) -> None:
    file_path = str(root / "proj" / "x.py")
    tree = _tree("def go(): pass\n")
    reg = SuppressionRegistry(
        entries=(
            SuppressionEntry(
                fqn="proj.x.go",
                code="SL001",
                reason="r",
            ),
        )
    )
    findings = scan_stale_registry(
        reg,
        file_path=file_path,
        project_root=str(root),
        analyzer_findings=[GuidanceFinding(line=1, code="SL001", message="x")],
        tree=tree,
    )
    assert all(f.code != "SL204" for f in findings)


def test_entry_for_different_module_ignored(root: Path) -> None:
    file_path = str(root / "proj" / "x.py")
    tree = _tree("def go(): pass\n")
    reg = SuppressionRegistry(
        entries=(
            SuppressionEntry(
                fqn="proj.other.go",
                code="SL001",
                reason="r",
            ),
        )
    )
    findings = scan_stale_registry(
        reg,
        file_path=file_path,
        project_root=str(root),
        analyzer_findings=[],
        tree=tree,
    )
    # FQN does not match this file's module; not stale relative to *this* file.
    assert all(f.code != "SL204" for f in findings)


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
    tree = _tree("")
    reg = SuppressionRegistry(
        entries=(
            SuppressionEntry(
                fqn="pkg.submodule.x",
                code="SL001",
                reason="r",
            ),
        )
    )
    findings = scan_stale_registry(
        reg,
        file_path=file_path,
        project_root=str(root),
        analyzer_findings=[],
        tree=tree,
    )
    assert all(f.code != "SL204" for f in findings)


def test_pg204_fires_per_construct_not_per_code(root: Path) -> None:
    """SL204 must match per construct, not just per code.

    The registry entry targets ``proj.x.other`` but the analyzer fires
    on a *different* construct in the same file. Pre-fix behavior
    collapsed all findings to a code-set, masking the stale entry.
    """
    file_path = str(root / "proj" / "x.py")
    tree = _tree("def one(): pass\ndef other(): pass\n")
    reg = SuppressionRegistry(
        entries=(
            SuppressionEntry(
                fqn="proj.x.other",
                code="SL001",
                reason="r",
            ),
        )
    )
    # Analyzer fires SL001 on `one`, not `other`.
    findings = scan_stale_registry(
        reg,
        file_path=file_path,
        project_root=str(root),
        analyzer_findings=[GuidanceFinding(line=1, code="SL001", message="x")],
        tree=tree,
    )
    assert any(f.code == "SL204" and "proj.x.other" in f.message for f in findings)


def test_pg204_reports_construct_line_not_file_top(root: Path) -> None:
    """SL204 finding line/col point at the stale construct, not file top.

    Pre-fix behavior always reported ``line=1, col=0`` regardless of
    where the construct lives in the file. The fix uses ``FQNResolver``
    to map the entry's FQN back to its AST node.
    """
    file_path = str(root / "proj" / "x.py")
    src = (
        "# leading comment\n"  # line 1
        "\n"  # line 2
        "def one(): pass\n"  # line 3
        "def two(): pass\n"  # line 4
    )
    tree = _tree(src)
    reg = SuppressionRegistry(
        entries=(
            SuppressionEntry(
                fqn="proj.x.two",
                code="SL001",
                reason="r",
            ),
        )
    )
    findings = scan_stale_registry(
        reg,
        file_path=file_path,
        project_root=str(root),
        analyzer_findings=[],
        tree=tree,
    )
    pg204 = [f for f in findings if f.code == "SL204"]
    assert len(pg204) == 1
    assert (pg204[0].line, pg204[0].col) == (4, 0)
