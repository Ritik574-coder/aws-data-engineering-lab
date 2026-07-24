"""argparse entry point for checking bucket existence."""

from __future__ import annotations

import sys

from s3_learning.cli import argparse_bucket_exists


if __name__ == "__main__":
    sys.exit(argparse_bucket_exists())

