"""Supyrliminal CLI umbrella — forwards to subcommands.

Entry point for the ``supyrliminal`` and ``sl`` scripts. Subcommands
dispatch to dedicated modules; this file is the routing layer only.
"""

import argparse
import sys

from supyrliminal._scan_config_cli import main as scan_config_main


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="supyrliminal",
        description="Supyrliminal — boundary-aware Pydantic guidance linter.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print Supyrliminal version and exit.",
    )
    sub = parser.add_subparsers(dest="command", required=False)

    scan = sub.add_parser(
        "scan-config",
        help="Scan a project for SL/PYD suppressions in config files.",
    )
    scan.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Project root to scan (default: current directory).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.version:
        from importlib.metadata import version

        print(f"supyrliminal {version('supyrliminal')}")
        return 0
    if args.command == "scan-config":
        from pathlib import Path

        return scan_config_main([str(Path(args.root).resolve())])
    _build_parser().print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
