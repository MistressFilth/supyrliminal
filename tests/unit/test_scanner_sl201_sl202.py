import ast

from supyrliminal._models import GuidanceFinding
from supyrliminal._suppression_scanner import scan_comments


def _scan(src: str) -> list[GuidanceFinding]:
    return scan_comments(ast.parse(src), src)


def test_blanket_noqa_emits_pg201() -> None:
    src = "x = 1  # noqa\n"
    findings = _scan(src)
    codes = {f.code for f in findings}
    assert "SL201" in codes
    assert all(f.line == 1 for f in findings if f.code == "SL201")


def test_specific_noqa_does_not_emit_pg201() -> None:
    src = "x = 1  # noqa: SL001\n"
    findings = _scan(src)
    assert all(f.code != "SL201" for f in findings)


def test_three_codes_emits_pg202() -> None:
    src = "x = 1  # noqa: SL001, SL002, SL003\n"
    findings = _scan(src)
    codes = {f.code for f in findings}
    assert "SL202" in codes


def test_two_codes_does_not_emit_pg202() -> None:
    src = "x = 1  # noqa: SL001, SL002\n"
    findings = _scan(src)
    assert all(f.code != "SL202" for f in findings)


def test_three_codes_mixed_pyd_emits_pg202() -> None:
    src = "x = 1  # noqa: SL001, PYD001, PYD002\n"
    findings = _scan(src)
    assert any(f.code == "SL202" for f in findings)


def test_non_pg_pyd_codes_do_not_trigger_pg202() -> None:
    """SL202 only counts PG/PYD codes; noqa for other families is out of scope."""
    src = "x = 1  # noqa: E501, W391, F401\n"
    findings = _scan(src)
    assert all(f.code != "SL202" for f in findings)


def test_noqa_not_present_emits_nothing() -> None:
    src = "x = 1  # this is fine\n"
    findings = _scan(src)
    assert findings == []
