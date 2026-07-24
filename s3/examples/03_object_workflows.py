"""Object upload, metadata, tags, presigned URL, and cleanup example."""

from __future__ import annotations

import logging
from pathlib import Path

from s3_learning.config import AppConfig
from s3_learning.logging_utils import configure_logging
from s3_learning.objects import S3ObjectManager
from s3_learning.session import AwsSessionFactory

logger = logging.getLogger(__name__)


def main() -> None:
    """Upload and inspect a local file in S3."""

    configure_logging()
    config = AppConfig.from_env()
    if not config.default_bucket:
        raise ValueError("Set S3LAB_DEFAULT_BUCKET before running this example")
    path = Path("assets/sample-object.txt")
    if not path.exists():
        path.write_text("sample object for S3 learning\n", encoding="utf-8")
    manager = S3ObjectManager(AwsSessionFactory(config).client("s3"), requester_pays=config.requester_pays)
    key = "examples/sample-object.txt"
    manager.upload_file(
        config.default_bucket,
        key,
        path,
        metadata={"purpose": "learning", "classification": "public-example"},
        tags={"project": "s3-learning", "environment": "sandbox"},
    )
    logger.info("Object metadata", extra={"metadata": manager.read_metadata(config.default_bucket, key)})
    logger.info("Object tags", extra={"tags": manager.get_object_tags(config.default_bucket, key)})
    logger.info("Presigned URL", extra={"url": manager.presigned_get_url(config.default_bucket, key)})


if __name__ == "__main__":
    main()

