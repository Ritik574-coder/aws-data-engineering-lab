"""Backup automation example using recursive upload.

Production backup tools need dry-run, encryption, retention, restore testing,
and clear failure reporting. This example keeps the upload logic reusable and
leaves scheduling to cron, Airflow, Step Functions, or another orchestrator.
"""

from __future__ import annotations

import logging
from pathlib import Path

from s3_learning.config import AppConfig
from s3_learning.logging_utils import configure_logging
from s3_learning.objects import S3ObjectManager
from s3_learning.session import AwsSessionFactory

logger = logging.getLogger(__name__)


def backup_directory(local_root: Path, bucket: str, prefix: str) -> int:
    """Upload a directory tree to a backup prefix."""

    config = AppConfig.from_env()
    manager = S3ObjectManager(AwsSessionFactory(config).client("s3"), requester_pays=config.requester_pays)
    return manager.recursive_upload(bucket, local_root, prefix)


def main() -> None:
    """Run backup from `local-data` to the default bucket."""

    configure_logging()
    config = AppConfig.from_env()
    if not config.default_bucket:
        raise ValueError("Set S3LAB_DEFAULT_BUCKET before running this example")
    uploaded = backup_directory(Path("local-data"), config.default_bucket, "backups/local-data")
    logger.info("Backup complete", extra={"uploaded": uploaded})


if __name__ == "__main__":
    main()

