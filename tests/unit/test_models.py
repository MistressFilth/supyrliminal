import pytest
from pydantic import ValidationError

from pydantic_guidance._models import SuppressionEntry, SuppressionRegistry


def test_suppression_entry_minimum_fields() -> None:
    entry = SuppressionEntry(
        fqn="myapp.legacy.parse",
        code="PG001",
        reason="per-call adapter needed",
        approved_by="alice",
        approved_sha="abc1234",
    )
    assert entry.fqn == "myapp.legacy.parse"
    assert entry.code == "PG001"


def test_suppression_entry_missing_field_fails() -> None:
    with pytest.raises(ValidationError):
        SuppressionEntry(fqn="x", code="PG001")  # type: ignore[call-arg]


def test_registry_rejects_duplicate_fqn_code() -> None:
    a = SuppressionEntry(
        fqn="myapp.x",
        code="PG001",
        reason="r",
        approved_by="alice",
        approved_sha="a",
    )
    b = SuppressionEntry(
        fqn="myapp.x",
        code="PG001",
        reason="r2",
        approved_by="bob",
        approved_sha="b",
    )
    with pytest.raises(ValidationError):
        SuppressionRegistry(entries=(a, b))


def test_registry_allows_distinct_codes_same_fqn() -> None:
    a = SuppressionEntry(
        fqn="myapp.x",
        code="PG001",
        reason="r1",
        approved_by="alice",
        approved_sha="a",
    )
    b = SuppressionEntry(
        fqn="myapp.x",
        code="PG002",
        reason="r2",
        approved_by="alice",
        approved_sha="a",
    )
    reg = SuppressionRegistry(entries=(a, b))
    assert len(reg.entries) == 2
