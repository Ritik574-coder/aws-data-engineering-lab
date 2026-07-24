"""Show the current AWS identity.

Use this before risky S3 operations to confirm account, role, and principal.
The example uses the repository session factory so profiles, regions, retries,
and environment settings are consistent across all examples.
"""

from __future__ import annotations

import logging

from s3_learning.config import AppConfig
from s3_learning.logging_utils import configure_logging
from s3_learning.session import AwsSessionFactory

logger = logging.getLogger(__name__)


def main() -> None:
    """Print the current AWS caller identity."""

    configure_logging()
    config = AppConfig.from_env()
    identity = AwsSessionFactory(config).identity()
    logger.info("Resolved identity", extra={"account": identity.account, "arn": identity.arn})
    print(identity)


if __name__ == "__main__":
    main()

