"""unittest-style example for teams maintaining legacy test suites."""

from __future__ import annotations

import unittest
from datetime import date

from s3_learning.datalake import DataLakeObjectKey


class DataLakeKeyTest(unittest.TestCase):
    """Demonstrate equivalent coverage with unittest."""

    def test_key_contains_layer(self) -> None:
        """Generated key should start with the requested lake layer."""

        key = DataLakeObjectKey("bronze", "ops", "logs", date(2026, 7, 22), "logs.jsonl").as_key()
        self.assertTrue(key.startswith("bronze/"))


if __name__ == "__main__":
    unittest.main()

