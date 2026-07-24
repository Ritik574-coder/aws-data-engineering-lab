"""Object, prefix, metadata, tag, and transfer operations for Amazon S3."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError

from s3_learning.errors import raise_s3_runtime_error

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class S3ObjectInfo:
    """Object listing result."""

    key: str
    size: int
    etag: str
    last_modified: str
    storage_class: str


class S3ObjectManager:
    """Production-oriented wrapper for common S3 object workflows."""

    def __init__(self, s3_client: Any, *, requester_pays: bool = False) -> None:
        """Initialize the object manager."""

        self.s3 = s3_client
        self.requester_pays = requester_pays

    def upload_file(
        self,
        bucket: str,
        key: str,
        path: Path,
        *,
        metadata: dict[str, str] | None = None,
        tags: dict[str, str] | None = None,
        storage_class: str | None = None,
        sse: str | None = "AES256",
    ) -> None:
        """Upload a local file with metadata, tags, storage class, and encryption."""

        if not path.is_file():
            raise FileNotFoundError(path)
        extra: dict[str, Any] = {}
        if metadata:
            extra["Metadata"] = metadata
        if tags:
            extra["Tagging"] = "&".join(f"{name}={value}" for name, value in tags.items())
        if storage_class:
            extra["StorageClass"] = storage_class
        if sse:
            extra["ServerSideEncryption"] = sse
        try:
            self.s3.upload_file(
                Filename=str(path),
                Bucket=bucket,
                Key=key,
                ExtraArgs=extra or None,
                Config=default_transfer_config(),
            )
            logger.info("Uploaded file", extra={"bucket": bucket, "key": key, "path": str(path)})
        except ClientError as exc:
            raise_s3_runtime_error("upload_file", exc)

    def download_file(self, bucket: str, key: str, path: Path) -> None:
        """Download an S3 object to a local path, creating parent directories."""

        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.s3.download_file(Bucket=bucket, Key=key, Filename=str(path), Config=default_transfer_config())
            logger.info("Downloaded file", extra={"bucket": bucket, "key": key, "path": str(path)})
        except ClientError as exc:
            raise_s3_runtime_error("download_file", exc)

    def list_objects(self, bucket: str, prefix: str = "") -> list[S3ObjectInfo]:
        """List all objects under a prefix using pagination."""

        objects: list[S3ObjectInfo] = []
        try:
            paginator = self.s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix, **self._payer()):
                for item in page.get("Contents", []):
                    objects.append(
                        S3ObjectInfo(
                            key=item["Key"],
                            size=int(item["Size"]),
                            etag=item["ETag"].strip('"'),
                            last_modified=item["LastModified"].isoformat(),
                            storage_class=item.get("StorageClass", "STANDARD"),
                        )
                    )
            return objects
        except ClientError as exc:
            raise_s3_runtime_error("list_objects", exc)

    def copy_object(
        self,
        source_bucket: str,
        source_key: str,
        destination_bucket: str,
        destination_key: str,
        *,
        replace_metadata: dict[str, str] | None = None,
    ) -> None:
        """Copy an object. Rename and move workflows are copy plus delete."""

        args: dict[str, Any] = {
            "Bucket": destination_bucket,
            "Key": destination_key,
            "CopySource": {"Bucket": source_bucket, "Key": source_key},
        }
        if replace_metadata is not None:
            args["MetadataDirective"] = "REPLACE"
            args["Metadata"] = replace_metadata
        try:
            self.s3.copy_object(**args)
            logger.info("Copied object", extra={"source": source_key, "destination": destination_key})
        except ClientError as exc:
            raise_s3_runtime_error("copy_object", exc)

    def move_object(self, source_bucket: str, source_key: str, destination_bucket: str, destination_key: str) -> None:
        """Move an object by copying it and deleting the original."""

        self.copy_object(source_bucket, source_key, destination_bucket, destination_key)
        self.delete_object(source_bucket, source_key)

    def delete_object(self, bucket: str, key: str, *, version_id: str | None = None) -> None:
        """Delete an object or one specific version."""

        args: dict[str, Any] = {"Bucket": bucket, "Key": key}
        if version_id:
            args["VersionId"] = version_id
        try:
            self.s3.delete_object(**args)
            logger.info("Deleted object", extra={"bucket": bucket, "key": key, "version_id": version_id})
        except ClientError as exc:
            raise_s3_runtime_error("delete_object", exc)

    def recursive_upload(self, bucket: str, local_root: Path, prefix: str = "") -> int:
        """Upload all files below a local directory."""

        if not local_root.is_dir():
            raise NotADirectoryError(local_root)
        uploaded = 0
        for path in local_root.rglob("*"):
            if path.is_file():
                relative = path.relative_to(local_root).as_posix()
                key = f"{prefix.rstrip('/')}/{relative}" if prefix else relative
                self.upload_file(bucket, key, path)
                uploaded += 1
        return uploaded

    def recursive_download(self, bucket: str, prefix: str, local_root: Path) -> int:
        """Download all objects under an S3 prefix."""

        count = 0
        for obj in self.list_objects(bucket, prefix):
            destination = local_root / obj.key.removeprefix(prefix).lstrip("/")
            self.download_file(bucket, obj.key, destination)
            count += 1
        return count

    def create_folder_marker(self, bucket: str, prefix: str) -> None:
        """Create a zero-byte folder marker object for UI compatibility."""

        key = prefix.rstrip("/") + "/"
        try:
            self.s3.put_object(Bucket=bucket, Key=key, Body=b"")
            logger.info("Created folder marker", extra={"bucket": bucket, "key": key})
        except ClientError as exc:
            raise_s3_runtime_error("create_folder_marker", exc)

    def read_metadata(self, bucket: str, key: str) -> dict[str, str]:
        """Read custom user metadata from an object."""

        try:
            response = self.s3.head_object(Bucket=bucket, Key=key, **self._payer())
            return dict(response.get("Metadata", {}))
        except ClientError as exc:
            raise_s3_runtime_error("read_metadata", exc)

    def replace_metadata(self, bucket: str, key: str, metadata: dict[str, str]) -> None:
        """Replace object metadata using a self-copy."""

        self.copy_object(bucket, key, bucket, key, replace_metadata=metadata)

    def put_object_tags(self, bucket: str, key: str, tags: dict[str, str]) -> None:
        """Create or replace object tags."""

        try:
            self.s3.put_object_tagging(
                Bucket=bucket,
                Key=key,
                Tagging={"TagSet": [{"Key": name, "Value": value} for name, value in tags.items()]},
            )
        except ClientError as exc:
            raise_s3_runtime_error("put_object_tags", exc)

    def get_object_tags(self, bucket: str, key: str) -> dict[str, str]:
        """Return object tags as a dictionary."""

        try:
            response = self.s3.get_object_tagging(Bucket=bucket, Key=key)
            return {item["Key"]: item["Value"] for item in response.get("TagSet", [])}
        except ClientError as exc:
            raise_s3_runtime_error("get_object_tags", exc)

    def presigned_get_url(self, bucket: str, key: str, *, expires_seconds: int = 900) -> str:
        """Generate a presigned download URL."""

        try:
            return str(
                self.s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": bucket, "Key": key, **self._payer()},
                    ExpiresIn=expires_seconds,
                )
            )
        except ClientError as exc:
            raise_s3_runtime_error("presigned_get_url", exc)

    def bulk_delete(self, bucket: str, keys: Iterable[str], *, dry_run: bool = True) -> int:
        """Delete many objects in batches of 1000."""

        batch: list[dict[str, str]] = []
        deleted = 0
        for key in keys:
            batch.append({"Key": key})
            if len(batch) == 1000:
                deleted += self._delete_batch(bucket, batch, dry_run=dry_run)
                batch = []
        if batch:
            deleted += self._delete_batch(bucket, batch, dry_run=dry_run)
        return deleted

    def _delete_batch(self, bucket: str, batch: list[dict[str, str]], *, dry_run: bool) -> int:
        """Delete one batch of object identifiers."""

        if dry_run:
            logger.info("Dry-run bulk delete", extra={"bucket": bucket, "count": len(batch)})
            return len(batch)
        try:
            self.s3.delete_objects(Bucket=bucket, Delete={"Objects": batch})
            return len(batch)
        except ClientError as exc:
            raise_s3_runtime_error("bulk_delete", exc)

    def _payer(self) -> dict[str, str]:
        """Return RequestPayer parameters for requester-pays buckets."""

        return {"RequestPayer": "requester"} if self.requester_pays else {}


def default_transfer_config() -> TransferConfig:
    """Return a transfer configuration suitable for large object examples."""

    return TransferConfig(
        multipart_threshold=64 * 1024 * 1024,
        multipart_chunksize=16 * 1024 * 1024,
        max_concurrency=8,
        use_threads=True,
    )

