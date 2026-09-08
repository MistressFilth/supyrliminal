"""Tests for FQN derivation from AST and module paths."""

import ast
from pathlib import Path

from supyrliminal._fqn import FQNResolver, module_path


def _parse(src: str) -> ast.Module:
    return ast.parse(src)


def test_module_path_simple() -> None:
    assert module_path(Path("/repo/myapp/legacy.py"), Path("/repo")) == "myapp.legacy"


def test_module_path_init_py_collapsed() -> None:
    assert (
        module_path(Path("/repo/myapp/pkg/__init__.py"), Path("/repo")) == "myapp.pkg"
    )


def test_module_path_outside_root() -> None:
    assert module_path(Path("/other/x.py"), Path("/repo")) is None


def test_module_path_pyi() -> None:
    assert module_path(Path("/repo/myapp/legacy.pyi"), Path("/repo")) == "myapp.legacy"


def test_resolver_top_level_function() -> None:
    tree = _parse("def parse(): pass\n")
    r = FQNResolver(tree, "myapp.legacy")
    assert r.for_line(1) == "myapp.legacy.parse"


def test_resolver_method() -> None:
    src = "class A:\n    def m(self): pass\n"
    tree = _parse(src)
    r = FQNResolver(tree, "myapp.x")
    assert r.for_line(2) == "myapp.x.A.m"


def test_resolver_nested_class() -> None:
    src = "class A:\n    class B:\n        def c(self): pass\n"
    tree = _parse(src)
    r = FQNResolver(tree, "myapp.x")
    assert r.for_line(3) == "myapp.x.A.B.c"


def test_resolver_async_function() -> None:
    tree = _parse("async def go(): pass\n")
    r = FQNResolver(tree, "myapp.x")
    assert r.for_line(1) == "myapp.x.go"


def test_resolver_decorator_targets_decorated_function() -> None:
    src = "class A:\n    @staticmethod\n    def m(): pass\n"
    tree = _parse(src)
    r = FQNResolver(tree, "myapp.x")
    # Line 2 is the @staticmethod decorator, line 3 is `def m`.
    assert r.for_line(2) == "myapp.x.A.m"
    assert r.for_line(3) == "myapp.x.A.m"


def test_resolver_module_scope() -> None:
    tree = _parse("X = 1\n")
    r = FQNResolver(tree, "myapp.x")
    assert r.for_line(1) == "myapp.x"
