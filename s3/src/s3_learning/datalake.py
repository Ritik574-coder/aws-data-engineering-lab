"""Data lake naming, partitioning, and object key design utilities."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import PurePosixPath

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DataLakeObjectKey:
    """Structured S3 key for bronze, silver, and gold data lake objects."""

    layer: str
    domain: str
    dataset: str
    load_date: date
    file_name: str

    def as_key(self) -> str:
        """Render the data lake key using Hive-compatible date partitions."""

        if self.layer not in {"bronze", "silver", "gold"}:
            raise ValueError("layer must be one of bronze, silver, or gold")
        path = PurePosixPath(
            self.layer,
            self.domain,
            self.dataset,
            f"year={self.load_date:%Y}",
            f"month={self.load_date:%m}",
            f"day={self.load_date:%d}",
            self.file_name,
        )
        key = path.as_posix()
        logger.debug("Generated data lake key", extra={"key": key})
        return key


def recommended_file_format(layer: str) -> str:
    """Return a recommended storage format for a data lake layer."""

    recommendations = {
        "bronze": "compressed-jsonl-or-parquet",
        "silver": "snappy-parquet",
        "gold": "snappy-parquet-or-table-format",
    }
    try:
        return recommendations[layer]
    except KeyError as exc:
        raise ValueError("Unknown data lake layer") from exc

