"""Command-line interface for the S3 learning repository."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import click
from rich.console import Console

from s3_learning.buckets import S3BucketManager
from s3_learning.config import AppConfig
from s3_learning.logging_utils import configure_logging
from s3_learning.objects import S3ObjectManager
from s3_learning.session import AwsSessionFactory

logger = logging.getLogger(__name__)
console = Console()


@click.group()
@click.option("--log-level", default="INFO", show_default=True)
def main(log_level: str) -> None:
    """Production Amazon S3 learning CLI."""

    configure_logging(log_level)


@main.command("identity")
def identity_command() -> None:
    """Show current AWS caller identity."""

    config = AppConfig.from_env()
    identity = AwsSessionFactory(config).identity()
    console.print({"account": identity.account, "arn": identity.arn, "user_id": identity.user_id})


@main.command("bucket-stats")
@click.argument("bucket")
@click.option("--prefix", default="", show_default=True)
def bucket_stats_command(bucket: str, prefix: str) -> None:
    """Show approximate object count and bytes for a bucket prefix."""

    config = AppConfig.from_env()
    factory = AwsSessionFactory(config)
    manager = S3BucketManager(factory.client("s3"), config.aws_region)
    stats = manager.statistics(bucket, prefix)
    console.print(stats)


@main.command("upload")
@click.argument("bucket")
@click.argument("key")
@click.argument("path", type=click.Path(path_type=Path, exists=True))
def upload_command(bucket: str, key: str, path: Path) -> None:
    """Upload one file to S3."""

    config = AppConfig.from_env()
    factory = AwsSessionFactory(config)
    S3ObjectManager(factory.client("s3"), requester_pays=config.requester_pays).upload_file(bucket, key, path)


def argparse_bucket_exists(argv: list[str] | None = None) -> int:
    """argparse example that checks bucket existence.

    The project includes both click and argparse because production teams often
    maintain both modern and legacy command-line tools.
    """

    parser = argparse.ArgumentParser(description="Check if an S3 bucket exists.")
    parser.add_argument("bucket")
    args = parser.parse_args(argv)
    configure_logging("INFO")
    config = AppConfig.from_env()
    factory = AwsSessionFactory(config)
    manager = S3BucketManager(factory.client("s3"), config.aws_region)
    exists = manager.bucket_exists(args.bucket)
    logger.info("Bucket existence check complete", extra={"bucket": args.bucket, "exists": exists})
    return 0 if exists else 2


if __name__ == "__main__":
    main()

