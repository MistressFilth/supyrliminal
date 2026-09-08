"""Pytest configuration: re-exports BDD step fixtures into the conftest namespace."""

from __future__ import annotations

from tests.features.steps import test_suppression_scanner_steps

# Re-export each BDD step fixture under its `pytestbdd_stepdef_*` name so pytest
# treats the fixtures as defined in this conftest (visible to all tests under
# tests/features/). pytest-bdd's @given decorator registers fixtures in the
# caller module's namespace; the steps module is not directly visible from
# tests/features/test_suppression_scanner.py, so we mirror the fixtures here.
_fixtures_module = test_suppression_scanner_steps
for _name in list(vars(_fixtures_module)):
    if _name.startswith("pytestbdd_stepdef_"):
        globals()[_name] = getattr(_fixtures_module, _name)
    if _name == "ctx":
        globals()[_name] = getattr(_fixtures_module, _name)
del _name, _fixtures_module
