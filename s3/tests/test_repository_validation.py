"""Tests for repository structure validation utility."""

from __future__ import annotations

from pathlib import Path

from utilities.validate_repository import validate


def test_repository_structure_is_present() -> None:
    """The generated repository should include all required top-level paths."""

    assert validate(Path.cwd()) == []

