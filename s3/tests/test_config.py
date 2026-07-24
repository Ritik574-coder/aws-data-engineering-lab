"""Tests for configuration loading.

These tests prevent accidental regressions in environment and INI parsing,
which matters because wrong regions or dry-run settings can cause production
operations to run against the wrong account or with unsafe behavior.
"""

from __future__ import annotations

from pathlib import Path

from s3_learning.config import AppConfig


def test_config_from_ini(tmp_path: Path) -> None:
    """INI configuration should be parsed and validated."""

    config_path = tmp_path / "config.ini"
    config_path.write_text(
        "\n".join(
            [
                "[default]",
                "aws_profile = analytics",
                "aws_region = us-west-2",
                "default_bucket = example-bucket",
                "requester_pays = true",
                "dry_run = false",
                "max_attempts = 5",
            ]
        ),
        encoding="utf-8",
    )
    config = AppConfig.from_ini(config_path)
    assert config.aws_profile == "analytics"
    assert config.aws_region == "us-west-2"
    assert config.default_bucket == "example-bucket"
    assert config.requester_pays is True
    assert config.dry_run is False
    assert config.max_attempts == 5

