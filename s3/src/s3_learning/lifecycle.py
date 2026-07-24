"""Lifecycle, versioning, object lock, inventory, and storage class examples."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from botocore.exceptions import ClientError

from s3_learning.errors import raise_s3_runtime_error

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StorageClassProfile:
    """Teaching model for storage class tradeoffs."""

    name: str
    best_for: str
    limitations: str
    cost_note: str


STORAGE_CLASSES: tuple[StorageClassProfile, ...] = (
    StorageClassProfile("STANDARD", "frequently accessed durable data", "highest storage cost", "no retrieval fee"),
    StorageClassProfile("EXPRESS_ONEZONE", "latency-sensitive single-AZ workloads", "single AZ", "premium performance pricing"),
    StorageClassProfile("INTELLIGENT_TIERING", "unknown access patterns", "monitoring charge for eligible objects", "automatic tiering"),
    StorageClassProfile("STANDARD_IA", "infrequent access multi-AZ data", "retrieval fee and minimum duration", "lower storage price"),
    StorageClassProfile("ONEZONE_IA", "re-creatable infrequent data", "single AZ durability model", "lower than Standard-IA"),
    StorageClassProfile("GLACIER_IR", "archive with millisecond retrieval", "minimum duration", "archive storage plus retrieval costs"),
    StorageClassProfile("GLACIER", "minutes-to-hours archive", "restore required", "low storage, restore fees"),
    StorageClassProfile("DEEP_ARCHIVE", "long-term cold archive", "hours restore latency", "lowest storage cost"),
)


class S3LifecycleManager:
    """Manage versioning, lifecycle, inventory, and restore configuration."""

    def __init__(self, s3_client: Any) -> None:
        """Initialize lifecycle manager."""

        self.s3 = s3_client

    def enable_versioning(self, bucket: str) -> None:
        """Enable versioning for overwrite and delete protection."""

        try:
            self.s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
        except ClientError as exc:
            raise_s3_runtime_error("enable_versioning", exc)

    def suspend_versioning(self, bucket: str) -> None:
        """Suspend future version creation while retaining existing versions."""

        try:
            self.s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Suspended"})
        except ClientError as exc:
            raise_s3_runtime_error("suspend_versioning", exc)

    def apply_data_lake_lifecycle(self, bucket: str) -> None:
        """Apply a practical lifecycle policy for data lake prefixes."""

        rules = [
            {
                "ID": "bronze-raw-retain-and-tier",
                "Status": "Enabled",
                "Filter": {"Prefix": "bronze/"},
                "Transitions": [{"Days": 30, "StorageClass": "STANDARD_IA"}, {"Days": 180, "StorageClass": "GLACIER"}],
                "NoncurrentVersionExpiration": {"NoncurrentDays": 90},
                "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
            },
            {
                "ID": "tmp-expire",
                "Status": "Enabled",
                "Filter": {"Prefix": "tmp/"},
                "Expiration": {"Days": 7},
                "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1},
            },
        ]
        try:
            self.s3.put_bucket_lifecycle_configuration(Bucket=bucket, LifecycleConfiguration={"Rules": rules})
        except ClientError as exc:
            raise_s3_runtime_error("apply_data_lake_lifecycle", exc)

    def restore_glacier_object(self, bucket: str, key: str, *, days: int = 7, tier: str = "Standard") -> None:
        """Request temporary restoration of an archived object."""

        try:
            self.s3.restore_object(
                Bucket=bucket,
                Key=key,
                RestoreRequest={"Days": days, "GlacierJobParameters": {"Tier": tier}},
            )
        except ClientError as exc:
            raise_s3_runtime_error("restore_glacier_object", exc)

    def configure_inventory(self, bucket: str, destination_bucket_arn: str, account_id: str) -> None:
        """Enable a weekly inventory report in Parquet format."""

        config = {
            "Destination": {
                "S3BucketDestination": {
                    "AccountId": account_id,
                    "Bucket": destination_bucket_arn,
                    "Format": "Parquet",
                    "Prefix": "inventory/",
                }
            },
            "IsEnabled": True,
            "Id": "weekly-parquet-inventory",
            "IncludedObjectVersions": "All",
            "Schedule": {"Frequency": "Weekly"},
            "OptionalFields": ["Size", "LastModifiedDate", "StorageClass", "ETag", "EncryptionStatus", "ObjectLockRetainUntilDate"],
        }
        try:
            self.s3.put_bucket_inventory_configuration(
                Bucket=bucket,
                Id="weekly-parquet-inventory",
                InventoryConfiguration=config,
            )
        except ClientError as exc:
            raise_s3_runtime_error("configure_inventory", exc)

