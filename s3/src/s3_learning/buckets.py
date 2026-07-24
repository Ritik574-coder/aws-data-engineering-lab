"""Bucket management operations for Amazon S3.

This module teaches safe bucket automation: create, inspect, list, empty, delete,
and collect simple statistics. Bucket deletion and emptying are intentionally
explicit because production data loss usually comes from broad recursive actions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from botocore.exceptions import ClientError

from s3_learning.errors import parse_client_error, raise_s3_runtime_error

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BucketSummary:
    """Small bucket summary returned by list operations."""

    name: str
    creation_date: str


@dataclass(frozen=True)
class BucketStatistics:
    """Approximate bucket statistics from paginated object listing."""

    bucket: str
    object_count: int
    total_bytes: int


class S3BucketManager:
    """Reusable bucket management wrapper around the S3 client."""

    def __init__(self, s3_client: Any, region_name: str) -> None:
        """Initialize with a boto3 S3 client and target region."""

        self.s3 = s3_client
        self.region_name = region_name

    def create_bucket(self, bucket: str) -> None:
        """Create a bucket using correct region-specific API behavior."""

        try:
            if self.region_name == "us-east-1":
                self.s3.create_bucket(Bucket=bucket)
            else:
                self.s3.create_bucket(
                    Bucket=bucket,
                    CreateBucketConfiguration={"LocationConstraint": self.region_name},
                )
            self.s3.get_waiter("bucket_exists").wait(Bucket=bucket)
            logger.info("Created bucket", extra={"bucket": bucket})
        except ClientError as exc:
            raise_s3_runtime_error("create_bucket", exc)

    def bucket_exists(self, bucket: str) -> bool:
        """Return whether a bucket exists and is accessible."""

        try:
            self.s3.head_bucket(Bucket=bucket)
            return True
        except ClientError as exc:
            details = parse_client_error(exc)
            if details.code in {"404", "NoSuchBucket", "NotFound"}:
                return False
            if details.code in {"403", "AccessDenied"}:
                logger.warning("Bucket exists but access is denied", extra={"bucket": bucket})
                return True
            raise_s3_runtime_error("bucket_exists", exc)

    def bucket_region(self, bucket: str) -> str:
        """Return the bucket region, normalizing the legacy us-east-1 response."""

        try:
            response = self.s3.get_bucket_location(Bucket=bucket)
            return response.get("LocationConstraint") or "us-east-1"
        except ClientError as exc:
            raise_s3_runtime_error("bucket_region", exc)

    def list_buckets(self) -> list[BucketSummary]:
        """List buckets visible to the current principal."""

        try:
            response = self.s3.list_buckets()
            return [
                BucketSummary(name=item["Name"], creation_date=item["CreationDate"].isoformat())
                for item in response.get("Buckets", [])
            ]
        except ClientError as exc:
            raise_s3_runtime_error("list_buckets", exc)

    def empty_bucket(self, bucket: str, *, include_versions: bool = True, dry_run: bool = True) -> int:
        """Delete all objects from a bucket, optionally including versions.

        Args:
            bucket: Bucket to empty.
            include_versions: Whether to delete object versions and delete markers.
            dry_run: When true, only count objects that would be deleted.

        Returns:
            Number of object identifiers deleted or planned for deletion.
        """

        deleted = 0
        if include_versions:
            paginator = self.s3.get_paginator("list_object_versions")
            for page in paginator.paginate(Bucket=bucket):
                keys = [
                    {"Key": item["Key"], "VersionId": item["VersionId"]}
                    for item in page.get("Versions", []) + page.get("DeleteMarkers", [])
                ]
                deleted += self._delete_key_batch(bucket, keys, dry_run=dry_run)
        else:
            paginator = self.s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket):
                keys = [{"Key": item["Key"]} for item in page.get("Contents", [])]
                deleted += self._delete_key_batch(bucket, keys, dry_run=dry_run)
        logger.info("Bucket empty operation complete", extra={"bucket": bucket, "count": deleted})
        return deleted

    def delete_bucket(self, bucket: str, *, empty_first: bool = False, dry_run: bool = True) -> None:
        """Delete a bucket after optional emptying."""

        if empty_first:
            self.empty_bucket(bucket, include_versions=True, dry_run=dry_run)
        if dry_run:
            logger.info("Dry-run delete bucket", extra={"bucket": bucket})
            return
        try:
            self.s3.delete_bucket(Bucket=bucket)
            self.s3.get_waiter("bucket_not_exists").wait(Bucket=bucket)
            logger.info("Deleted bucket", extra={"bucket": bucket})
        except ClientError as exc:
            raise_s3_runtime_error("delete_bucket", exc)

    def statistics(self, bucket: str, prefix: str = "") -> BucketStatistics:
        """Calculate object count and total size under a prefix."""

        count = 0
        total = 0
        try:
            paginator = self.s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for item in page.get("Contents", []):
                    count += 1
                    total += int(item["Size"])
            return BucketStatistics(bucket=bucket, object_count=count, total_bytes=total)
        except ClientError as exc:
            raise_s3_runtime_error("statistics", exc)

    def _delete_key_batch(self, bucket: str, keys: list[dict[str, str]], *, dry_run: bool) -> int:
        """Delete up to 1000 object identifiers using DeleteObjects."""

        if not keys:
            return 0
        if dry_run:
            logger.info("Dry-run delete object batch", extra={"bucket": bucket, "count": len(keys)})
            return len(keys)
        try:
            for start in range(0, len(keys), 1000):
                self.s3.delete_objects(Bucket=bucket, Delete={"Objects": keys[start : start + 1000]})
            return len(keys)
        except ClientError as exc:
            raise_s3_runtime_error("delete_key_batch", exc)

