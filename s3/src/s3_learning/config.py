"""Application configuration for Amazon S3 examples.

The module centralizes environment, INI, and CLI configuration because
production S3 tooling usually runs in many places: laptops, CI systems,
containers, schedulers, and ephemeral incident-response shells.
"""

from __future__ import annotations

import configparser
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class AppConfig(BaseModel):
    """Validated runtime settings for S3 automation.

    Attributes:
        aws_profile: Optional AWS named profile.
        aws_region: AWS region used for regional clients and bucket creation.
        default_bucket: Optional bucket used by examples.
        assume_role_arn: Optional role ARN for STS AssumeRole examples.
        mfa_serial: Optional MFA device ARN or serial number.
        requester_pays: Whether requests should include RequestPayer.
        dry_run: Whether destructive commands should only report intended work.
        max_attempts: Botocore retry attempt limit.
    """

    aws_profile: str | None = Field(default=None)
    aws_region: str = Field(default="us-east-1")
    default_bucket: str | None = Field(default=None)
    assume_role_arn: str | None = Field(default=None)
    mfa_serial: str | None = Field(default=None)
    requester_pays: bool = Field(default=False)
    dry_run: bool = Field(default=True)
    max_attempts: int = Field(default=10, ge=1, le=20)

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "AppConfig":
        """Build configuration from `.env` and process environment values.

        Args:
            env_file: Optional path to a dotenv file.

        Returns:
            Validated application configuration.

        Raises:
            ValueError: If values fail validation.
        """

        if env_file:
            load_dotenv(env_file)
            logger.debug("Loaded environment file", extra={"env_file": str(env_file)})
        else:
            load_dotenv()
            logger.debug("Loaded default dotenv file if present")

        raw: dict[str, Any] = {
            "aws_profile": os.getenv("AWS_PROFILE") or None,
            "aws_region": os.getenv("AWS_REGION", "us-east-1"),
            "default_bucket": os.getenv("S3LAB_DEFAULT_BUCKET") or None,
            "assume_role_arn": os.getenv("S3LAB_ASSUME_ROLE_ARN") or None,
            "mfa_serial": os.getenv("S3LAB_MFA_SERIAL") or None,
            "requester_pays": _parse_bool(os.getenv("S3LAB_REQUESTER_PAYS"), False),
            "dry_run": _parse_bool(os.getenv("S3LAB_DRY_RUN"), True),
            "max_attempts": int(os.getenv("S3LAB_MAX_ATTEMPTS", "10")),
        }
        try:
            return cls(**raw)
        except ValidationError as exc:
            logger.exception("Invalid S3 lab configuration")
            raise ValueError("Invalid S3 lab configuration") from exc

    @classmethod
    def from_ini(cls, path: Path, section: str = "default") -> "AppConfig":
        """Build configuration from an INI file.

        Args:
            path: Config file path.
            section: INI section to load.

        Returns:
            Validated application configuration.

        Raises:
            FileNotFoundError: If the config file does not exist.
            KeyError: If the section is missing.
            ValueError: If values fail validation.
        """

        if not path.exists():
            logger.error("Configuration file does not exist", extra={"path": str(path)})
            raise FileNotFoundError(path)
        parser = configparser.ConfigParser()
        parser.read(path)
        if section not in parser:
            logger.error("Configuration section is missing", extra={"section": section})
            raise KeyError(section)
        values = parser[section]
        try:
            return cls(
                aws_profile=values.get("aws_profile") or None,
                aws_region=values.get("aws_region", "us-east-1"),
                default_bucket=values.get("default_bucket") or None,
                assume_role_arn=values.get("assume_role_arn") or None,
                mfa_serial=values.get("mfa_serial") or None,
                requester_pays=values.getboolean("requester_pays", fallback=False),
                dry_run=values.getboolean("dry_run", fallback=True),
                max_attempts=values.getint("max_attempts", fallback=10),
            )
        except ValidationError as exc:
            logger.exception("Invalid INI configuration", extra={"path": str(path)})
            raise ValueError("Invalid INI configuration") from exc


def _parse_bool(value: str | None, default: bool) -> bool:
    """Parse common environment boolean values."""

    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}

