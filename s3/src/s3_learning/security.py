"""Security controls for S3 buckets."""

from __future__ import annotations

import json
import logging
from typing import Any

from botocore.exceptions import ClientError

from s3_learning.errors import raise_s3_runtime_error

logger = logging.getLogger(__name__)


class S3SecurityManager:
    """Manage common S3 security settings using explicit APIs."""

    def __init__(self, s3_client: Any) -> None:
        """Initialize the security manager."""

        self.s3 = s3_client

    def enable_block_public_access(self, bucket: str) -> None:
        """Enable all S3 Block Public Access settings on a bucket."""

        try:
            self.s3.put_public_access_block(
                Bucket=bucket,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": True,
                    "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True,
                    "RestrictPublicBuckets": True,
                },
            )
            logger.info("Enabled block public access", extra={"bucket": bucket})
        except ClientError as exc:
            raise_s3_runtime_error("enable_block_public_access", exc)

    def enforce_bucket_owner(self, bucket: str) -> None:
        """Disable ACL-based ownership complexity with bucket-owner-enforced mode."""

        try:
            self.s3.put_bucket_ownership_controls(
                Bucket=bucket,
                OwnershipControls={"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]},
            )
        except ClientError as exc:
            raise_s3_runtime_error("enforce_bucket_owner", exc)

    def enable_default_encryption(self, bucket: str, kms_key_id: str | None = None) -> None:
        """Enable default bucket encryption with SSE-S3 or SSE-KMS."""

        rule: dict[str, Any] = {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
        if kms_key_id:
            rule = {
                "ApplyServerSideEncryptionByDefault": {
                    "SSEAlgorithm": "aws:kms",
                    "KMSMasterKeyID": kms_key_id,
                },
                "BucketKeyEnabled": True,
            }
        try:
            self.s3.put_bucket_encryption(
                Bucket=bucket,
                ServerSideEncryptionConfiguration={"Rules": [rule]},
            )
        except ClientError as exc:
            raise_s3_runtime_error("enable_default_encryption", exc)

    def apply_tls_only_policy(self, bucket: str) -> None:
        """Apply a bucket policy that denies non-TLS requests."""

        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "DenyInsecureTransport",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:*",
                    "Resource": [f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"],
                    "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                }
            ],
        }
        try:
            self.s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
        except ClientError as exc:
            raise_s3_runtime_error("apply_tls_only_policy", exc)

