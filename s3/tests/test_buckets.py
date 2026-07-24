"""Unit tests for S3 bucket management with moto."""

from __future__ import annotations

from typing import Any

from s3_learning.buckets import S3BucketManager


def test_create_exists_stats_and_empty_bucket(s3_client: Any, bucket_name: str) -> None:
    """Bucket manager should create, inspect, count, and empty objects safely."""

    manager = S3BucketManager(s3_client, "us-east-1")
    assert manager.bucket_exists(bucket_name) is False
    manager.create_bucket(bucket_name)
    assert manager.bucket_exists(bucket_name) is True
    s3_client.put_object(Bucket=bucket_name, Key="a.txt", Body=b"a")
    s3_client.put_object(Bucket=bucket_name, Key="nested/b.txt", Body=b"bb")
    stats = manager.statistics(bucket_name)
    assert stats.object_count == 2
    assert stats.total_bytes == 3
    assert manager.empty_bucket(bucket_name, include_versions=False, dry_run=True) == 2
    assert manager.empty_bucket(bucket_name, include_versions=False, dry_run=False) == 2
    assert manager.statistics(bucket_name).object_count == 0

