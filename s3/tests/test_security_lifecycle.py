"""Tests for security and lifecycle configuration APIs.

Moto supports enough of these APIs to verify request construction. Real AWS
integration tests are still needed before applying controls to production
accounts because policies, KMS, Object Ownership, and lifecycle timing have
service-side behavior beyond unit tests.
"""

from __future__ import annotations

from typing import Any

from s3_learning.lifecycle import S3LifecycleManager, STORAGE_CLASSES
from s3_learning.security import S3SecurityManager


def test_security_and_lifecycle_configuration(s3_client: Any, bucket_name: str) -> None:
    """Security baseline and lifecycle rule calls should be accepted."""

    s3_client.create_bucket(Bucket=bucket_name)
    security = S3SecurityManager(s3_client)
    lifecycle = S3LifecycleManager(s3_client)
    security.enable_block_public_access(bucket_name)
    security.enable_default_encryption(bucket_name)
    security.apply_tls_only_policy(bucket_name)
    lifecycle.enable_versioning(bucket_name)
    lifecycle.apply_data_lake_lifecycle(bucket_name)
    assert any(profile.name == "INTELLIGENT_TIERING" for profile in STORAGE_CLASSES)

