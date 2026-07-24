"""Tests for data lake key generation and recommendations."""

from __future__ import annotations

from datetime import date

import pytest

from s3_learning.datalake import DataLakeObjectKey, recommended_file_format


def test_data_lake_key_uses_hive_partitions() -> None:
    """Generated keys should be stable and query-engine friendly."""

    key = DataLakeObjectKey(
        layer="silver",
        domain="finance",
        dataset="transactions",
        load_date=date(2026, 7, 22),
        file_name="part-0001.parquet",
    ).as_key()
    assert key == "silver/finance/transactions/year=2026/month=07/day=22/part-0001.parquet"


def test_unknown_layer_is_rejected() -> None:
    """Invalid layers should fail early instead of creating bad S3 layouts."""

    with pytest.raises(ValueError):
        DataLakeObjectKey(
            layer="raw",
            domain="finance",
            dataset="transactions",
            load_date=date(2026, 7, 22),
            file_name="part-0001.parquet",
        ).as_key()


def test_recommended_file_format() -> None:
    """Each lake layer should have an explicit format recommendation."""

    assert recommended_file_format("gold") == "snappy-parquet-or-table-format"

