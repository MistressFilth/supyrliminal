"""Pure AST analyzer for Supyrliminal (SL) findings.

The analyzer is the single brain of the SL linter: it takes a parsed
``ast.Module`` and returns a deduped, ordered list of ``GuidanceFinding``
objects. It does not invoke flake8, pydantic validation, or I/O; the
``GuidanceFinding`` carrier is the only outbound dependency. The
``flake8_supyrliminal`` plugin wraps it as the yield source for ``run()``.
"""

import ast

from supyrliminal._model_detect import (
    collect_basemodel_names,
    is_basemodel_class,
    is_rootmodel_class,
    resolves_to_name,
    uses_pydantic_surface,
)
from supyrliminal._models import GuidanceFinding

_SL001_MSG = (
    "SL001 TypeAdapter constructed inside a function — "
    "build it once at module scope and reuse it"
)
_SL002_MSG = (
    "SL002 TypeAdapter used as a field annotation — "
    "use RootModel for a reusable named root type; TypeAdapter is a tool, not a field type"
)
_SL003_MSG = (
    "SL003 deprecated @root_validator — use @model_validator(mode='before'|'after')"
)
_SL101_MSG = (
    "SL101 BaseModel uses no Pydantic surface — "
    "if this is internal code-built state, a stdlib @dataclass is lighter"
)

_TYPEADAPTER = frozenset({"TypeAdapter"})
_ROOT_VALIDATOR = frozenset({"root_validator"})


def _check_sl001(tree: ast.Module) -> list[GuidanceFinding]:
    """Flag ``TypeAdapter(...)`` constructed inside a function body.

    Module-scope construction is the performant pattern; a call inside a
    function rebuilds the adapter on every invocation. A single ``ast.walk``
    pass flags a ``TypeAdapter(...)`` call iff an enclosing
    ``FunctionDef``/``AsyncFunctionDef`` exists (tracked via a parent map
    built once), avoiding the redundant nested re-walk of the prior
    implementation.
    """
    findings: list[GuidanceFinding] = []
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent

    def _enclosed_in_function(node: ast.AST) -> bool:
        cursor: ast.AST | None = parents.get(id(node))
        while cursor is not None:
            if isinstance(cursor, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return True
            cursor = parents.get(id(cursor))
        return False

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and resolves_to_name(node.func, _TYPEADAPTER)
            and _enclosed_in_function(node)
        ):
            findings.append(
                GuidanceFinding(
                    line=node.lineno,
                    col=node.col_offset,
                    code="SL001",
                    message=_SL001_MSG,
                )
            )
    return findings


def _check_sl002(tree: ast.Module, known: frozenset[str]) -> list[GuidanceFinding]:
    """Flag ``TypeAdapter`` used as a field annotation inside a Pydantic model.

    A ``TypeAdapter`` is a validation tool, not a type; a field annotation
    referencing it misrepresents the model's shape. Use ``RootModel[T]`` for a
    reusable named root type.
    """
    findings: list[GuidanceFinding] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and is_basemodel_class(node, known)):
            continue
        for item in node.body:
            if (
                isinstance(item, ast.AnnAssign)
                and item.annotation is not None
                and resolves_to_name(item.annotation, _TYPEADAPTER)
            ):
                findings.append(
                    GuidanceFinding(
                        line=item.annotation.lineno,
                        col=item.annotation.col_offset,
                        code="SL002",
                        message=_SL002_MSG,
                    )
                )
    return findings


def _check_sl003(tree: ast.Module) -> list[GuidanceFinding]:
    """Flag the deprecated ``@root_validator`` decorator (any form)."""
    findings: list[GuidanceFinding] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if resolves_to_name(dec, _ROOT_VALIDATOR):
                findings.append(
                    GuidanceFinding(
                        line=dec.lineno,
                        col=dec.col_offset,
                        code="SL003",
                        message=_SL003_MSG,
                    )
                )
    return findings


def _check_sl101(tree: ast.Module, known: frozenset[str]) -> list[GuidanceFinding]:
    """Soft-hint flag: a ``BaseModel`` subclass using no Pydantic surface.

    A model that declares no ``model_config``, ``Field(...)``, ``Annotated``
    field, validator/serializer decorator, ``__pydantic_extra__``, or
    ``model_*`` override carries none of Pydantic's value-add. RootModel
    subclasses are excused. The hint is opt-in via flake8 ``--extend-select``.
    """
    findings: list[GuidanceFinding] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and is_basemodel_class(node, known)):
            continue
        if is_rootmodel_class(node):
            continue
        if uses_pydantic_surface(node):
            continue
        findings.append(
            GuidanceFinding(
                line=node.lineno,
                col=node.col_offset,
                code="SL101",
                message=_SL101_MSG,
            )
        )
    return findings


def analyze(tree: ast.Module) -> list[GuidanceFinding]:
    """Return all SL findings for a single module AST, deduped and ordered.

    Findings are sorted by ``(line, col, code)`` and de-duplicated on the same
    triple, so a ``TypeAdapter`` call nested under several enclosing function
    walks is reported once.

    Args:
        tree: A parsed ``ast.Module``.

    Returns:
        An ordered list of ``GuidanceFinding`` with no duplicate
        ``(line, col, code)`` triples.
    """
    known = collect_basemodel_names(tree)
    findings: list[GuidanceFinding] = []
    findings.extend(_check_sl001(tree))
    findings.extend(_check_sl002(tree, known))
    findings.extend(_check_sl003(tree))
    findings.extend(_check_sl101(tree, known))
    seen: set[tuple[int, int, str]] = set()
    unique: list[GuidanceFinding] = []
    for f in sorted(findings, key=lambda f: (f.line, f.col, f.code)):
        key = (f.line, f.col, f.code)
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique
