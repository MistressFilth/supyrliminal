"""FQN derivation for the suppression registry.

FQN keys are AST-stable identifiers: ``module``, ``module.func``,
``module.Class.method``, ``module.Class.Nested``. They never encode line
numbers so that editing a construct below an existing one does not
invalidate the registry.

Module path derivation drops the project root, strips the suffix,
collapses ``__init__`` segments entirely, and joins the remaining parts
with ``.``. The result is the dotted module name; the FQN is the module
path plus the smallest enclosing ``ClassDef`` / ``FunctionDef`` /
``AsyncFunctionDef`` chain found in the AST.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SUFFIXES = (".py", ".pyi")


def module_path(file: Path, root: Path) -> str | None:
    """Return the dotted module path of ``file`` within ``root``.

    Returns ``None`` if ``file`` is not under ``root``. ``__init__``
    segments are removed entirely, so a package's ``__init__.py`` and
    the package itself share a module path.
    """
    try:
        rel = file.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    parts = list(rel.parts)
    if parts and parts[-1].endswith(_SUFFIXES):
        last = parts[-1]
        for suf in _SUFFIXES:
            if last.endswith(suf):
                last = last[: -len(suf)]
                break
        parts[-1] = last
    parts = [p for p in parts if p and p != "__init__"]
    return ".".join(parts) if parts else None


class FQNResolver:
    """Resolve the smallest enclosing FQN for any line of a parsed AST.

    Constructed with the parsed tree and the module path. ``for_line``
    walks the parent map from any node covering the requested line back
    to ``Module``, collecting the names of enclosing ``ClassDef`` /
    ``FunctionDef`` / ``AsyncFunctionDef`` scopes along the way.
    """

    def __init__(self, tree: ast.AST, module: str) -> None:
        self._module = module
        self._tree = tree
        parents: dict[int, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[id(child)] = parent
        self._parents = parents

    def for_line(self, line: int) -> str:
        """Return the FQN of the smallest enclosing construct for ``line``.

        Module-level (no enclosing function/class) returns the module
        path itself. Lines outside the file's source range also resolve
        to the module path.
        """
        # BFS via ast.walk visits parents before children, so the last
        # node that covers ``line`` is the deepest (most nested) one.
        anchor: ast.AST | None = None
        for node in ast.walk(self._tree):
            if _covers(node, line):
                anchor = node
        if anchor is None:
            return self._module
        chain: list[str] = []
        cur: ast.AST | None = anchor
        while cur is not None:
            if isinstance(cur, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                chain.append(cur.name)
            cur = self._parents.get(id(cur))
        if not chain:
            return self._module
        chain.reverse()
        return f"{self._module}." + ".".join(chain)


def _covers(node: ast.AST, line: int) -> bool:
    """True iff ``line`` falls inside ``node``'s source range."""
    start = getattr(node, "lineno", None)
    end = getattr(node, "end_lineno", None)
    if start is None:
        return False
    if end is None:
        return line == start
    return start <= line <= end
