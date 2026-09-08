import pytest
from pydantic import ValidationError

from supyrliminal._models import SuppressionEntry, SuppressionRegistry


def test_suppression_entry_minimum_fields() -> None:
    entry = SuppressionEntry(
        fqn="myapp.legacy.parse",
        code="SL001",
        reason="per-call adapter needed",
    )
    assert entry.fqn == "myapp.legacy.parse"
    assert entry.code == "SL001"


def test_suppression_entry_missing_field_fails() -> None:
    with pytest.raises(ValidationError):
        SuppressionEntry(fqn="x", code="SL001")  # type: ignore[call-arg]


def test_registry_rejects_duplicate_fqn_code() -> None:
    a = SuppressionEntry(
        fqn="myapp.x",
        code="SL001",
        reason="r",
    )
    b = SuppressionEntry(
        fqn="myapp.x",
        code="SL001",
        reason="r2",
    )
    with pytest.raises(ValidationError):
        SuppressionRegistry(entries=(a, b))


def test_registry_allows_distinct_codes_same_fqn() -> None:
    a = SuppressionEntry(
        fqn="myapp.x",
        code="SL001",
        reason="r1",
    )
    b = SuppressionEntry(
        fqn="myapp.x",
        code="SL002",
        reason="r2",
    )
    reg = SuppressionRegistry(entries=(a, b))
    assert len(reg.entries) == 2
