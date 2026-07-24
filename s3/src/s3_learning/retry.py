"""Small application-level retry helper for idempotent workflows."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import TypeVar

from botocore.exceptions import ClientError

from s3_learning.errors import is_retryable_client_error

logger = logging.getLogger(__name__)
T = TypeVar("T")


def retry_client_error(
    operation: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay_seconds: float = 0.25,
    max_delay_seconds: float = 4.0,
) -> T:
    """Retry an idempotent AWS operation with exponential backoff and jitter.

    Botocore already retries many service calls. This helper is for higher-level
    idempotent workflows where an operation may include multiple API calls.
    """

    last_error: ClientError | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except ClientError as exc:
            last_error = exc
            if attempt >= attempts or not is_retryable_client_error(exc):
                logger.exception("AWS operation failed without retrying further")
                raise
            delay = min(max_delay_seconds, base_delay_seconds * (2 ** (attempt - 1)))
            sleep_seconds = random.uniform(0, delay)
            logger.warning(
                "Retrying AWS operation after retryable failure",
                extra={"attempt": attempt, "sleep_seconds": sleep_seconds},
            )
            time.sleep(sleep_seconds)
    if last_error is not None:
        raise last_error
    raise RuntimeError("Retry helper was called with no attempts")

