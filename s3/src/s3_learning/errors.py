"""Error handling helpers for AWS S3 operations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import NoReturn

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


RETRYABLE_ERROR_CODES = {
    "RequestTimeout",
    "SlowDown",
    "Throttling",
    "ThrottlingException",
    "TooManyRequestsException",
    "InternalError",
    "ServiceUnavailable",
}


@dataclass(frozen=True)
class AwsErrorDetails:
    """Normalized fields from a botocore ClientError."""

    code: str
    message: str
    request_id: str | None
    host_id: str | None


def parse_client_error(exc: ClientError) -> AwsErrorDetails:
    """Extract stable AWS error fields from a ClientError."""

    error = exc.response.get("Error", {})
    metadata = exc.response.get("ResponseMetadata", {})
    return AwsErrorDetails(
        code=str(error.get("Code", "Unknown")),
        message=str(error.get("Message", "")),
        request_id=metadata.get("RequestId"),
        host_id=metadata.get("HostId"),
    )


def is_retryable_client_error(exc: ClientError) -> bool:
    """Return true when the AWS error code is usually safe to retry."""

    return parse_client_error(exc).code in RETRYABLE_ERROR_CODES


def raise_s3_runtime_error(action: str, exc: ClientError) -> NoReturn:
    """Log rich AWS diagnostics and raise a RuntimeError."""

    details = parse_client_error(exc)
    logger.error(
        "S3 action failed",
        extra={
            "action": action,
            "aws_error_code": details.code,
            "request_id": details.request_id,
        },
    )
    raise RuntimeError(f"{action} failed with AWS error {details.code}: {details.message}") from exc

