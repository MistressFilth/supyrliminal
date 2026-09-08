"""Flake8 extension for pydantic-guidance (PG) enforcement."""

from __future__ import annotations

import argparse
import ast
import os
from collections.abc import Iterator
from importlib.metadata import version
from pathlib import Path
from typing import Any, Self

from pydantic_guidance._flake8_protocol import RESULT_ADAPTER
from pydantic_guidance._guidance_rules import analyze
from pydantic_guidance._models import GuidanceFinding, SuppressionRegistry
from pydantic_guidance._suppression_registry import load as load_registry
from pydantic_guidance._suppression_scanner import (
    scan_comments,
    scan_stale_registry,
)

_PY_SUFFIXES = (".py", ".pyi")


class PGPlugin:
    """Flake8 AST checker for pydantic-guidance.

    Emits PG001-003 (hard, default-on) and PG101 (soft, opt-in via
    ``--extend-select=PG101``). Also emits PG201-PG204 (hard, default-on)
    auditing every PG/PYD suppression in Python source, gated by a
    registry in ``pyproject.toml``. PG205 audits project settings and
    ships as a standalone ``pg-scan-config`` CLI because flake8's AST
    plugin protocol cannot reach ``.toml``/``.cfg``/``.ini`` files.
    The whole plugin is gated by ``[hooks].structured_data_enforcement``
    in ``.true-spec/project/true-spec.toml``.

    flake8 supplies ``filename`` to ``__init__`` from
    ``FileProcessor.filename`` per the documented plugin protocol
    (``docs/source/plugin-development/plugin-parameters.rst``).
    """

    name = "flake8-pydantic-guidance"
    version = version("pydantic-guidance")

    _enabled: bool = True
    _project_root: str = os.getcwd()
    _registry: SuppressionRegistry = SuppressionRegistry()

    def __init__(self, tree: ast.AST, filename: str) -> None:
        self._tree = tree
        self._filename = filename

    @staticmethod
    def _load_registry(root: Path) -> SuppressionRegistry:
        return load_registry(root)

    @classmethod
    def add_options(cls, option_manager: Any) -> None:
        try:
            option_manager.add_option(
                "--pg-config-root",
                default=None,
                parse_from_config=True,
                help=(
                    "Project root for pydantic-guidance config resolution. "
                    "Default: current working directory."
                ),
            )
        except argparse.ArgumentError:
            pass

    @classmethod
    def parse_options(cls, options: Any) -> None:
        from pydantic_guidance._config import read_hooks_config

        root = options.pg_config_root or os.getcwd()
        cls._enabled = read_hooks_config(root).structured_data_enforcement
        cls._project_root = root
        cls._registry = cls._load_registry(Path(root))

    def run(self) -> Iterator[tuple[int, int, str, type[Self]]]:
        if not self._enabled:
            return

        findings: list[GuidanceFinding] = []
        if isinstance(self._tree, ast.Module):
            findings.extend(self._run_python())

        for f in findings:
            yield RESULT_ADAPTER.validate_python((f.line, f.col, f.message, type(self)))

    def _run_python(self) -> Iterator[GuidanceFinding]:
        analyzer_findings = list(analyze(self._tree))  # type: ignore[arg-type]
        source = ""
        try:
            with open(self._filename, encoding="utf-8") as f:
                source = f.read()
        except UnicodeDecodeError:
            try:
                with open(self._filename, encoding="latin-1") as f:
                    source = f.read()
            except OSError:
                source = ""
        except OSError:
            source = ""
        yield from scan_comments(
            self._tree,  # type: ignore[arg-type]
            source,
            file_path=self._filename,
            project_root=self._project_root,
            registry=self._registry,
            analyzer_findings=analyzer_findings,
        )
        yield from scan_stale_registry(
            self._registry,
            file_path=self._filename,
            project_root=self._project_root,
            analyzer_findings=analyzer_findings,
        )
        yield from analyzer_findings
