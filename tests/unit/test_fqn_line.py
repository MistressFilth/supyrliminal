import ast

from supyrliminal._fqn import FQNResolver


def test_line_for_fqn_module_returns_first_line() -> None:
    tree = ast.parse("def go(): pass\n")
    r = FQNResolver(tree, "m")
    assert r.line_for_fqn("m") == (1, 0)


def test_line_for_fqn_top_level_function() -> None:
    src = "# header comment\n\ndef parse(x):\n    return x\n"
    r = FQNResolver(ast.parse(src), "m.legacy")
    line, col = r.line_for_fqn("m.legacy.parse")
    assert (line, col) == (3, 0)


def test_line_for_fqn_method_records_actual_col() -> None:
    src = "class A:\n    def m(self):\n        return 1\n"
    r = FQNResolver(ast.parse(src), "m.x")
    line, col = r.line_for_fqn("m.x.A.m")
    assert line == 2
    assert col > 0


def test_line_for_fqn_nested_class() -> None:
    src = "class A:\n    class B:\n        def c(self): pass\n"
    r = FQNResolver(ast.parse(src), "m.x")
    line, col = r.line_for_fqn("m.x.A.B.c")
    assert (line, col) == (3, 8)


def test_line_for_fqn_unknown_returns_none() -> None:
    tree = ast.parse("def parse(): pass\n")
    r = FQNResolver(tree, "m.legacy")
    assert r.line_for_fqn("m.legacy.does_not_exist") is None
    assert r.line_for_fqn("m.other.parse") is None
