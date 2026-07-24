"""Unit tests for S3 object workflows with moto."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from s3_learning.objects import S3ObjectManager


def test_upload_metadata_tags_copy_and_download(s3_client: Any, bucket_name: str, tmp_path: Path) -> None:
    """Object manager should handle core object lifecycle behavior."""

    s3_client.create_bucket(Bucket=bucket_name)
    source = tmp_path / "source.txt"
    source.write_text("hello s3", encoding="utf-8")
    manager = S3ObjectManager(s3_client)
    manager.upload_file(
        bucket_name,
        "folder/source.txt",
        source,
        metadata={"owner": "data-engineering"},
        tags={"environment": "test"},
    )
    assert manager.read_metadata(bucket_name, "folder/source.txt")["owner"] == "data-engineering"
    assert manager.get_object_tags(bucket_name, "folder/source.txt")["environment"] == "test"
    objects = manager.list_objects(bucket_name, "folder/")
    assert [item.key for item in objects] == ["folder/source.txt"]
    manager.copy_object(bucket_name, "folder/source.txt", bucket_name, "folder/copy.txt")
    destination = tmp_path / "downloads" / "copy.txt"
    manager.download_file(bucket_name, "folder/copy.txt", destination)
    assert destination.read_text(encoding="utf-8") == "hello s3"

