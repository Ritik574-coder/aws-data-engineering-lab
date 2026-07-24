"""S3 integration patterns for pandas, PyArrow, DuckDB, Polars, and PySpark.

The functions are intentionally small and documented because each engine has
different S3 filesystem behavior, dependency expectations, and memory tradeoffs.
"""

from __future__ import annotations

from pathlib import Path


def pandas_local_then_upload(path: Path) -> None:
    """Teach the safest beginner pattern: write locally, validate, then upload.

    Pandas can read and write S3 through optional filesystem dependencies, but
    production ETL jobs often benefit from explicit local staging, validation,
    and S3 upload through the shared object manager.
    """

    import pandas as pd

    df = pd.DataFrame([{"order_id": 1, "amount": 100.0}])
    df.to_parquet(path, index=False)


def duckdb_query_s3_uri(uri: str) -> object:
    """Return a DuckDB relation for an S3 URI.

    DuckDB can query Parquet data directly from S3 when its HTTPFS extension and
    credentials are configured. This function is a teaching stub so tests do not
    require network access.
    """

    import duckdb

    return duckdb.sql(f"select * from read_parquet('{uri}')")


def pyarrow_dataset_path(path: Path) -> object:
    """Load a local Parquet dataset with PyArrow before moving to S3 scale."""

    import pyarrow.dataset as ds

    return ds.dataset(path)


def polars_lazy_scan(path: Path) -> object:
    """Return a Polars lazy scan for efficient columnar processing."""

    import polars as pl

    return pl.scan_parquet(path)

