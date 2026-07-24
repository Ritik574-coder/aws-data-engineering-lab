"""Secure data lake bucket setup example.

The workflow enables versioning, Block Public Access, default encryption,
bucket-owner-enforced object ownership, TLS-only policy, and lifecycle rules.
Run in a sandbox account first.
"""

from __future__ import annotations

from s3_learning.config import AppConfig
from s3_learning.lifecycle import S3LifecycleManager
from s3_learning.logging_utils import configure_logging
from s3_learning.security import S3SecurityManager
from s3_learning.session import AwsSessionFactory


def main() -> None:
    """Apply secure baseline controls to `S3LAB_DEFAULT_BUCKET`."""

    configure_logging()
    config = AppConfig.from_env()
    if not config.default_bucket:
        raise ValueError("Set S3LAB_DEFAULT_BUCKET before running this example")
    s3 = AwsSessionFactory(config).client("s3")
    security = S3SecurityManager(s3)
    lifecycle = S3LifecycleManager(s3)
    security.enable_block_public_access(config.default_bucket)
    security.enforce_bucket_owner(config.default_bucket)
    security.enable_default_encryption(config.default_bucket)
    security.apply_tls_only_policy(config.default_bucket)
    lifecycle.enable_versioning(config.default_bucket)
    lifecycle.apply_data_lake_lifecycle(config.default_bucket)


if __name__ == "__main__":
    main()

