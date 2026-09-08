"""Linter models — GuidanceFinding, HooksConfig, RulesConfig, SuppressionEntry, SuppressionRegistry."""

from __future__ import annotations

import pydantic
from pydantic import BaseModel, ConfigDict


class GuidanceFinding(BaseModel):
    """A single pydantic-guidance finding emitted by the PG linter."""

    model_config = ConfigDict(frozen=True)

    line: int
    col: int = 0
    code: str
    message: str


class HooksConfig(BaseModel):
    """Typed configuration for the [hooks] section of .true-spec/project/true-spec.toml.

    Only ``structured_data_enforcement`` is read: it gates the whole PG
    plugin on or off. Safe defaults apply (enforcement on) when the TOML is
    absent or malformed.
    """

    model_config = ConfigDict(frozen=True)

    structured_data_enforcement: bool = True


class RulesConfig(BaseModel):
    """Typed configuration for the [rules] section of .true-spec/project/true-spec.toml.

    The legacy ``structured_data`` mode switch and ``allow_raw_collections``
    override are removed: the PG linter is boundary-aware and no longer gated
    by a pydantic-vs-dataclass mode. The class is retained so future advisory
    rule settings have a home.
    """

    model_config = ConfigDict(frozen=True)


class SuppressionEntry(BaseModel):
    """One authorized suppression, declared in pyproject.toml.

    ``fqn`` is the AST-stable identifier of the construct being suppressed
    (function, method, nested class, or module). ``code`` is the PG/PYD
    code authorized for that construct. ``approved_by`` and ``approved_sha``
    are an audit trail; the HITL gate is enforced via CODEOWNERS on
    ``pyproject.toml``, not by this model.
    """

    model_config = ConfigDict(frozen=True)

    fqn: str
    code: str
    reason: str
    approved_by: str
    approved_sha: str


class SuppressionRegistry(BaseModel):
    """The full registry as parsed from [tool.pydantic_guidance.suppressions].

    Duplicate ``(fqn, code)`` pairs are rejected: silent override would mask
    intent. The pair is the natural key.
    """

    model_config = ConfigDict(frozen=True)

    entries: tuple[SuppressionEntry, ...] = ()

    @pydantic.field_validator("entries")
    @classmethod
    def _no_duplicate_pairs(
        cls, entries: tuple[SuppressionEntry, ...]
    ) -> tuple[SuppressionEntry, ...]:
        seen: set[tuple[str, str]] = set()
        for e in entries:
            key = (e.fqn, e.code)
            if key in seen:
                msg = f"duplicate suppression entry for {key}"
                raise ValueError(msg)
            seen.add(key)
        return entries

    def find(self, fqn: str, code: str) -> SuppressionEntry | None:
        """Return the entry authorizing ``code`` on ``fqn``, or None."""
        for e in self.entries:
            if e.fqn == fqn and e.code == code:
                return e
        return None

    def fqns_for(self, code: str) -> frozenset[str]:
        """Return every FQN this registry authorizes for ``code``."""
        return frozenset(e.fqn for e in self.entries if e.code == code)
