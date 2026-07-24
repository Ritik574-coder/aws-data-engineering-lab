"""Bucket management example.

This file demonstrates existence checks, create bucket, statistics, and
dry-run deletion. Use a sandbox account because real buckets are billable and
bucket names are globally unique.
"""

from __future__ import annotations

import logging

from s3_learning.buckets import S3BucketManager
from s3_learning.config import AppConfig
from s3_learning.logging_utils import configure_logging
from s3_learning.session import AwsSessionFactory

logger = logging.getLogger(__name__)


def main() -> None:
    """Run bucket management workflow against `S3LAB_DEFAULT_BUCKET`."""

    configure_logging()
    config = AppConfig.from_env()
    if not config.default_bucket:
        raise ValueError("Set S3LAB_DEFAULT_BUCKET before running this example")
    factory = AwsSessionFactory(config)
    manager = S3BucketManager(factory.client("s3"), config.aws_region)
    if not manager.bucket_exists(config.default_bucket):
        manager.create_bucket(config.default_bucket)
    stats = manager.statistics(config.default_bucket)
    logger.info("Bucket statistics", extra={"objects": stats.object_count, "bytes": stats.total_bytes})


if __name__ == "__main__":
    main()

