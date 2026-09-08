"""Load the suppression registry from pyproject.toml.

The registry is the authorization back-end for every `# noqa: PGxxx` /
`# noqa: PYDxxx` comment. Every entry is reviewed via CODEOWNERS on
``pyproject.toml``; the linter only checks that comments match a
registry entry.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import ValidationError

from pydantic_guidance._models import SuppressionEntry, SuppressionRegistry


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
    try:
        return SuppressionRegistry(entries=tuple(entries))
    except ValidationError:
        return SuppressionRegistry(entries=tuple(entries[:0]))
