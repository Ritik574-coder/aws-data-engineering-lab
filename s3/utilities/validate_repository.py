"""Validate repository structure for the S3 learning project."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


REQUIRED_PATHS = [
    "README.md",
    "requirements.txt",
    "pyproject.toml",
    ".env.example",
    "LICENSE",
    "CHANGELOG.md",
    "docs",
    "examples",
    "src",
    "tests",
    "configs",
    "scripts",
    "utilities",
    "assets",
]


def validate(root: Path) -> list[str]:
    """Return missing required repository paths."""

    missing = [path for path in REQUIRED_PATHS if not (root / path).exists()]
    if missing:
        logger.error("Repository validation failed", extra={"missing": missing})
    return missing


def main() -> int:
    """Command-line validation entry point."""

    missing = validate(Path.cwd())
    if missing:
        print("Missing paths:")
        for path in missing:
            print(f"- {path}")
        return 1
    print("Repository structure is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

