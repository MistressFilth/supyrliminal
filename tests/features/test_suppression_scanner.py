"""Bind the suppression scanner feature file to pytest test functions."""

from __future__ import annotations

from pytest_bdd import scenarios

scenarios("suppression_scanner.feature")
