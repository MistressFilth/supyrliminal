"""Standalone scanner for SL205 — project-settings suppression scanner.

flake8 AST plugins cannot see config files (flake8 routes tree plugins
through ``ast.parse`` first, which raises ``SyntaxError`` on
``.toml``/``.cfg``/``.ini``). The SL205 scanner ships as a standalone
subcommand instead. Run it from the repo root:

    supyrliminal scan-config            # walk the current tree
    supyrliminal scan-config /path/to/project

Output is flake8-compatible (``path:line:col: CODE message``) so it can
be piped into any flake8-aware toolchain.
"""

import argparse
import sys
from pathlib import Path

from supyrliminal._config_scanner import _RECOGNIZED_NAMES, scan_config
from supyrliminal._models import GuidanceFinding


def _is_target(path: Path) -> bool:
    """True when ``path`` is a config file the scanner knows how to read."""
    if path.name in _RECOGNIZED_NAMES:
        return True
    return path.suffix.lower() in {".toml", ".cfg", ".ini", ".py", ".pyi"}


def scan_project(root: Path) -> list[GuidanceFinding]:
    """Walk ``root`` for recognized config files and emit SL205 findings.

    The walker descends into every directory below ``root``; hidden
    directories (``.git``, ``.venv``, etc.) are skipped. Each matched
    file is read once and passed to ``scan_config``.
    """
    findings: list[GuidanceFinding] = []
    if not root.exists() or not root.is_dir():
        return findings
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(
            part.startswith(".") and part not in _RECOGNIZED_NAMES
            for part in path.parts
        ):
            continue
        if not _is_target(path):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        findings.extend(scan_config(path, source))
    return findings


def _format_finding(path: Path, finding: GuidanceFinding) -> str:
    """Render a single finding in flake8's ``path:line:col: CODE message`` shape."""
    return f"{path}:{finding.line}:{finding.col}: {finding.code} {finding.message}"


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``supyrliminal scan-config`` subcommand."""
    parser = argparse.ArgumentParser(
        prog="supyrliminal scan-config",
        description=(
            "Scan a project for SL/PYD suppressions in config files "
            "(pyproject.toml, setup.cfg, .flake8, tox.ini, *.ini, and "
            "inline `# flake8:` blocks in Python files)."
        ),
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Project root to scan (default: current directory).",
    )
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    findings = scan_project(root)
    for finding in findings:
        print(_format_finding(root, finding))
    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main())
