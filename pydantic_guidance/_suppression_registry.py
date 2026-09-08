"""Load the suppression registry from pyproject.toml.

The registry is the authorization back-end for every `# noqa: PGxxx` /
`# noqa: PYDxxx` comment. Every entry is reviewed via CODEOWNERS on
``pyproject.toml``; the linter only checks that comments match a
registry entry.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from pydantic import ValidationError

from pydantic_guidance._models import SuppressionEntry, SuppressionRegistry


def _dedupe_valid(
    entries: list[SuppressionEntry],
) -> tuple[SuppressionEntry, ...]:
    """Filter duplicate ``(fqn, code)`` pairs; log a warning when any are dropped.

    The registry validator raises on the first duplicate; here we
    drop duplicates defensively so a single typo can't wipe every
    well-formed entry. A stderr line surfaces the count so the issue
    is visible without crashing the linter.
    """
    seen: set[tuple[str, str]] = set()
    kept: list[SuppressionEntry] = []
    dropped = 0
    for entry in entries:
        key = (entry.fqn, entry.code)
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        kept.append(entry)
    if dropped:
        print(
            f"pydantic-guidance: dropped {dropped} duplicate suppression "
            "entries (see [tool.pydantic_guidance.suppressions] in pyproject.toml)",
            file=sys.stderr,
        )
    return tuple(kept)


def load(root: Path) -> SuppressionRegistry:
    """Load `[tool.pydantic_guidance.suppressions]` from ``root/pyproject.toml``.

    Returns an empty registry when the file is absent, the section is
    absent, or parsing fails. Malformed entries are silently dropped
    (the per-entry error path is a follow-up — see spec "Future Work").
    """
    toml_path = root / "pyproject.toml"
    if not toml_path.exists():
        return SuppressionRegistry()
    try:
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError):
        return SuppressionRegistry()
    section = data.get("tool", {}).get("pydantic_guidance", {})
    raw = section.get("suppressions", [])
    if not isinstance(raw, list):
        return SuppressionRegistry()
    entries: list[SuppressionEntry] = []
    for item in raw:
        try:
            entries.append(SuppressionEntry.model_validate(item))
        except ValidationError:
            continue
    return SuppressionRegistry(entries=_dedupe_valid(entries))