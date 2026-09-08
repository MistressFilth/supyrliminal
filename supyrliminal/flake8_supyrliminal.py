"""Flake8 extension for Supyrliminal (SL) enforcement."""

import argparse
import ast
import os
from collections.abc import Iterator
from importlib.metadata import version
from pathlib import Path
from typing import Any, Self

from supyrliminal._flake8_protocol import RESULT_ADAPTER
from supyrliminal._guidance_rules import analyze
from supyrliminal._models import GuidanceFinding, SuppressionRegistry
from supyrliminal._suppression_registry import load as load_registry
from supyrliminal._suppression_scanner import (
    scan_comments,
    scan_stale_registry,
)


class SLPlugin:
    """Flake8 AST checker for Supyrliminal.

    Emits SL001-SL003 (hard, default-on) and SL101 (soft, opt-in via
    ``--extend-select=SL101``). Also emits SL201-SL204 (hard, default-on)
    auditing every SL/PYD suppression in Python source, gated by a
    registry in ``pyproject.toml``. SL205 audits project settings and
    ships under the ``supyrliminal scan-config`` CLI because flake8's AST
    plugin protocol cannot reach ``.toml``/``.cfg``/``.ini`` files.

    flake8 supplies ``filename`` to ``__init__`` from
    ``FileProcessor.filename`` per the documented plugin protocol
    (``docs/source/plugin-development/plugin-parameters.rst``).
    """

    name = "flake8-supyrliminal"
    version = version("supyrliminal")

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
                "--sl-config-root",
                default=None,
                parse_from_config=True,
                help=(
                    "Project root for Supyrliminal config resolution. "
                    "Default: current working directory."
                ),
            )
        except argparse.ArgumentError:
            pass

    @classmethod
    def parse_options(cls, options: Any) -> None:
        root = options.sl_config_root or os.getcwd()
        cls._project_root = root
        cls._registry = cls._load_registry(Path(root))

    def run(self) -> Iterator[tuple[int, int, str, type[Self]]]:
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
            tree=self._tree,  # type: ignore[arg-type]
        )
        yield from analyzer_findings
