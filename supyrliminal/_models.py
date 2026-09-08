"""Linter models — GuidanceFinding, SuppressionEntry, SuppressionRegistry."""

import pydantic
from pydantic import BaseModel, ConfigDict


class GuidanceFinding(BaseModel):
    """A single Supyrliminal finding emitted by the SL linter."""

    model_config = ConfigDict(frozen=True)

    line: int
    col: int = 0
    code: str
    message: str


class SuppressionEntry(BaseModel):
    """One authorized suppression, declared in pyproject.toml.

    ``fqn`` is the AST-stable identifier of the construct being suppressed
    (function, method, nested class, or module). ``code`` is the SL/PYD
    code authorized for that construct. The registry in ``pyproject.toml``
    is the auditable record.
    """

    model_config = ConfigDict(frozen=True)

    fqn: str
    code: str
    reason: str


class SuppressionRegistry(BaseModel):
    """The full registry as parsed from [tool.supyrliminal.suppressions].

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
