"""Shared pytest fixtures for S3 tests.

The tests use moto to emulate AWS APIs locally. Moto is excellent for unit
tests, but it does not perfectly reproduce every S3 edge case, permission
model, lifecycle delay, replication behavior, or KMS integration.
"""

from __future__ import annotations

from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws


@pytest.fixture()
def s3_client() -> Iterator[object]:
    """Return a moto-backed S3 client."""

    with mock_aws():
        yield boto3.client("s3", region_name="us-east-1")


@pytest.fixture()
def bucket_name() -> str:
    """Return a deterministic test bucket name."""

    return "s3-learning-test-bucket"

