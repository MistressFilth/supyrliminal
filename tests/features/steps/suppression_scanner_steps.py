"""Step definitions for the suppression scanner BDD feature."""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pytest_bdd import given, parsers, then, when

from pydantic_guidance._config_scanner import scan_config
from pydantic_guidance._models import (
    SuppressionEntry,
    SuppressionRegistry,
)
from pydantic_guidance._suppression_scanner import (
    scan_comments,
    scan_stale_registry,
)

if TYPE_CHECKING:
    from pydantic_guidance._models import GuidanceFinding


@pytest.fixture()
def ctx() -> dict:
    return {}


@given("a Python file with a blanket `# noqa`:")
def step_python_blanket(ctx: dict, docstring: str) -> None:
    ctx["source"] = docstring.strip("\n")
    ctx["filename"] = "/proj/legacy.py"
    ctx["root"] = "/proj"
    ctx["registry"] = SuppressionRegistry()


@given("a Python file with three PG/PYD codes in one noqa:")
def step_python_three_codes(ctx: dict, docstring: str) -> None:
    ctx["source"] = docstring.strip("\n")
    ctx["filename"] = "/proj/legacy.py"
    ctx["root"] = "/proj"
    ctx["registry"] = SuppressionRegistry()


@given("a Python file with an unauthorized noqa:")
def step_python_unauth(ctx: dict, docstring: str) -> None:
    ctx["source"] = docstring.strip("\n")
    ctx["filename"] = "/proj/legacy.py"
    ctx["root"] = "/proj"


@given("a Python file with a noqa:")
def step_python_authorized(ctx: dict, docstring: str) -> None:
    ctx["source"] = docstring.strip("\n")
    ctx["filename"] = "/proj/legacy.py"
    ctx["root"] = "/proj"


@given("an empty registry")
def step_empty_registry(ctx: dict) -> None:
    ctx["registry"] = SuppressionRegistry()


@given(parsers.parse('a registry entry authorizing "{fqn}" / "{code}"'))
def step_registry_entry(ctx: dict, fqn: str, code: str) -> None:
    ctx["registry"] = SuppressionRegistry(
        entries=(
            SuppressionEntry(
                fqn=fqn,
                code=code,
                reason="r",
                approved_by="alice",
                approved_sha="abc",
            ),
        )
    )


@given("a pyproject.toml with:")
def step_pyproject(ctx: dict, docstring: str) -> None:
    ctx["source"] = docstring.strip("\n")
    ctx["filename"] = "/proj/pyproject.toml"


@when("the file is scanned")
def step_scan(ctx: dict) -> None:
    source = ctx["source"]
    filename = ctx["filename"]
    root = ctx.get("root")
    registry = ctx.get("registry", SuppressionRegistry())
    if filename.endswith(".py"):
        tree = ast.parse(source)
        analyzer_findings: list[GuidanceFinding] = []
        comment_findings = scan_comments(
            tree,
            source,
            file_path=filename,
            project_root=root,
            registry=registry,
            analyzer_findings=analyzer_findings,
        )
        if root is None:
            stale_findings: list[GuidanceFinding] = []
        else:
            stale_findings = scan_stale_registry(
                registry,
                file_path=filename,
                project_root=root,
                analyzer_findings=analyzer_findings,
            )
        ctx["findings"] = comment_findings + stale_findings
    elif filename.endswith(".toml"):
        ctx["findings"] = scan_config(Path(filename), source)


@then(parsers.parse("PG201 fires on line {line:d}"))
def step_pg201(ctx: dict, line: int) -> None:
    assert any(f.code == "PG201" and f.line == line for f in ctx["findings"])


@then(parsers.parse("PG202 fires on line {line:d}"))
def step_pg202(ctx: dict, line: int) -> None:
    assert any(f.code == "PG202" and f.line == line for f in ctx["findings"])


@then(parsers.parse("PG203 fires on line {line:d}"))
def step_pg203(ctx: dict, line: int) -> None:
    assert any(f.code == "PG203" and f.line == line for f in ctx["findings"])


@then("PG203 does not fire")
def step_pg203_absent(ctx: dict) -> None:
    assert all(f.code != "PG203" for f in ctx["findings"])


@then(parsers.parse("PG205 fires for {code}"))
def step_pg205_for(ctx: dict, code: str) -> None:
    assert any(f.code == "PG205" and code in f.message for f in ctx["findings"])


@then(parsers.parse("PG205 does not fire for {code}"))
def step_pg205_absent_for(ctx: dict, code: str) -> None:
    assert all(not (f.code == "PG205" and code in f.message) for f in ctx["findings"])


@given("a project tree with pyproject.toml disabling PG001")
def step_project_with_disable(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.flake8]\nextend-ignore = "PG001, E501"\n',
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")


@when("pg-scan-config runs against the tree")
def step_pg_scan_config_runs(tmp_path: Path, ctx: dict) -> None:
    result = subprocess.run(
        ["pg-scan-config", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    ctx["cli_stdout"] = result.stdout
    ctx["cli_returncode"] = result.returncode


@then(parsers.parse("the CLI output mentions {code}"))
def step_cli_mentions(ctx: dict, code: str) -> None:
    assert code in ctx["cli_stdout"]
