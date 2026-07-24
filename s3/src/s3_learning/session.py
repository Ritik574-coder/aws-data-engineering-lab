"""AWS authentication and boto3 session construction examples.

This module teaches the credential provider chain, named profiles, STS
AssumeRole, and MFA. It avoids exposing secrets in logs and returns standard
boto3 sessions so all other modules can share the same authentication behavior.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from s3_learning.config import AppConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Identity:
    """Resolved AWS identity for audit-friendly diagnostics."""

    account: str
    arn: str
    user_id: str


class AwsSessionFactory:
    """Factory for boto3 sessions and service clients.

    Production tools should construct sessions in one place so retries, regions,
    profiles, and role assumption are applied consistently.
    """

    def __init__(self, config: AppConfig) -> None:
        """Initialize the session factory."""

        self.config = config
        self.botocore_config = Config(
            retries={"max_attempts": config.max_attempts, "mode": "standard"},
            region_name=config.aws_region,
            user_agent_extra="amazon-s3-production-engineering/0.1.0",
        )

    def base_session(self) -> boto3.Session:
        """Create a boto3 session from environment variables or a profile."""

        try:
            session = boto3.Session(
                profile_name=self.config.aws_profile,
                region_name=self.config.aws_region,
            )
            logger.debug("Created base AWS session", extra={"region": self.config.aws_region})
            return session
        except (BotoCoreError, Exception) as exc:
            logger.exception("Failed to create AWS session")
            raise RuntimeError("Failed to create AWS session") from exc

    def assumed_role_session(
        self,
        role_arn: str,
        session_name: str = "s3-learning-session",
        mfa_serial: str | None = None,
        mfa_token: str | None = None,
    ) -> boto3.Session:
        """Assume an IAM role and return a short-lived boto3 session.

        Args:
            role_arn: IAM role ARN to assume.
            session_name: STS session name for audit trails.
            mfa_serial: Optional MFA device ARN or serial.
            mfa_token: Optional MFA token code.

        Returns:
            boto3 session backed by temporary credentials.
        """

        sts = self.base_session().client("sts", config=self.botocore_config)
        request: dict[str, Any] = {"RoleArn": role_arn, "RoleSessionName": session_name}
        if mfa_serial and mfa_token:
            request["SerialNumber"] = mfa_serial
            request["TokenCode"] = mfa_token
        try:
            response = sts.assume_role(**request)
            credentials = response["Credentials"]
            logger.info("Assumed role successfully", extra={"role_arn": role_arn})
            return boto3.Session(
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
                region_name=self.config.aws_region,
            )
        except ClientError as exc:
            logger.exception("AssumeRole failed", extra={"role_arn": role_arn})
            raise RuntimeError(f"Unable to assume role {role_arn}") from exc

    def client(self, service_name: str, assumed: bool = False) -> Any:
        """Create a typed-at-runtime boto3 client with shared botocore config."""

        session = self.base_session()
        if assumed:
            if not self.config.assume_role_arn:
                raise ValueError("assume_role_arn is required when assumed=True")
            session = self.assumed_role_session(self.config.assume_role_arn)
        try:
            return session.client(service_name, config=self.botocore_config)
        except NoCredentialsError as exc:
            logger.exception("AWS credentials were not found")
            raise RuntimeError("AWS credentials were not found") from exc

    def identity(self) -> Identity:
        """Return the current caller identity from STS."""

        sts = self.client("sts")
        try:
            response = sts.get_caller_identity()
            return Identity(
                account=response["Account"],
                arn=response["Arn"],
                user_id=response["UserId"],
            )
        except ClientError as exc:
            logger.exception("Unable to resolve AWS caller identity")
            raise RuntimeError("Unable to resolve AWS caller identity") from exc

