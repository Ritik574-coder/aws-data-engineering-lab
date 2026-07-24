"""Generate production-style S3 keys for data lake objects."""

from __future__ import annotations

from datetime import date

from s3_learning.datalake import DataLakeObjectKey, recommended_file_format


def main() -> None:
    """Print sample bronze, silver, and gold keys."""

    for layer in ("bronze", "silver", "gold"):
        key = DataLakeObjectKey(
            layer=layer,
            domain="sales",
            dataset="orders",
            load_date=date(2026, 7, 22),
            file_name=f"orders-0001.{recommended_file_format(layer).split('-')[-1]}",
        ).as_key()
        print(key)


if __name__ == "__main__":
    main()

