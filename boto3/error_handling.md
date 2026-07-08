# Boto3 — Error Handling

## Service Overview

Boto3 errors fall into two categories: **ClientError** (AWS service returned an error response) and **BotoCoreError** (client-side issues like networking, credential resolution, or parsing).

Understanding error structure enables robust data pipelines that distinguish retryable throttling from permanent access denied failures.

**Error response structure:**

```python
exc.response["Error"]["Code"]       # e.g., "AccessDenied", "NoSuchKey"
exc.response["Error"]["Message"]    # Human-readable message
exc.response["ResponseMetadata"]["HTTPStatusCode"]
exc.response["ResponseMetadata"]["RequestId"]
```

---

## AWS CLI Commands

CLI errors mirror Boto3 ClientError codes. Enable debug for full HTTP traces:

```bash
aws s3 ls s3://nonexistent-bucket/ 2>&1
# An error occurred (NoSuchBucket) when calling the ListObjectsV2 operation: The specified bucket does not exist

aws s3 ls s3://restricted-bucket/ --debug 2>&1 | tail -50
```

---

## Advanced Commands

### Query Error Details with JMESPath

```bash
aws s3api head-object --bucket my-bucket --key missing.txt 2>&1 || true
```

### CLI Exit Codes

| Exit Code | Meaning |
|-----------|---------|
| 0 | Success |
| 254 | Command error (botocore exception) |
| 255 | General error |

Use in shell scripts:

```bash
if aws s3 cp s3://bucket/key /tmp/file 2>/dev/null; then
  echo "Download succeeded"
else
  echo "Download failed with exit code $?"
fi
```

---

## Python Boto3 Examples

### Basic ClientError Handling

```python
import boto3
from botocore.exceptions import ClientError

s3 = boto3.client("s3")

try:
    s3.head_object(Bucket="my-bucket", Key="orders/data.parquet")
except ClientError as exc:
    code = exc.response["Error"]["Code"]
    if code == "404":
        print("Object not found")
    elif code in ("403", "AccessDenied"):
        print("Access denied")
    else:
        raise
```

### Structured Error Handler

```python
import logging
from typing import Callable

from botocore.exceptions import ClientError, BotoCoreError

logger = logging.getLogger(__name__)

RETRYABLE_CODES = {
    "Throttling", "ThrottlingException", "RequestLimitExceeded",
    "ProvisionedThroughputExceededException", "ServiceUnavailable",
    "InternalServerError", "SlowDown",
}


def handle_aws_error(exc: Exception, *, context: str = "") -> None:
    if isinstance(exc, ClientError):
        code = exc.response["Error"]["Code"]
        message = exc.response["Error"]["Message"]
        request_id = exc.response["ResponseMetadata"].get("RequestId", "N/A")
        logger.error(
            "AWS error [%s] code=%s request_id=%s message=%s",
            context, code, request_id, message,
        )
        if code in RETRYABLE_CODES:
            raise  # let retry decorator handle
    elif isinstance(exc, BotoCoreError):
        logger.exception("BotoCore error [%s]", context)
    raise
```

### Decorator for Service Calls

```python
from functools import wraps

def aws_call(context: str = ""):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ClientError as exc:
                handle_aws_error(exc, context=context or func.__name__)
            except BotoCoreError:
                logger.exception("Network error in %s", context or func.__name__)
                raise
        return wrapper
    return decorator


@aws_call(context="upload_parquet")
def upload_parquet(s3, bucket: str, key: str, body: bytes) -> None:
    s3.put_object(Bucket=bucket, Key=key, Body=body, ServerSideEncryption="aws:kms")
```

### Idempotent Create Pattern

```python
def create_bucket_if_not_exists(s3, bucket: str, region: str) -> None:
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("404", "NoSuchBucket"):
            if region == "us-east-1":
                s3.create_bucket(Bucket=bucket)
            else:
                s3.create_bucket(
                    Bucket=bucket,
                    CreateBucketConfiguration={"LocationConstraint": region},
                )
        else:
            raise
```

### Collect Partial Batch Failures

```python
def delete_objects_safe(s3, bucket: str, keys: list[str]) -> tuple[int, list[str]]:
    response = s3.delete_objects(
        Bucket=bucket,
        Delete={"Objects": [{"Key": k} for k in keys], "Quiet": True},
    )
    deleted = len(response.get("Deleted", []))
    failed = [e["Key"] for e in response.get("Errors", [])]
    return deleted, failed
```

---

## Security Considerations

- Do not log full error responses in production — may contain resource ARNs with sensitive names.
- Log `RequestId` for AWS support tickets — not access keys or session tokens.
- Handle `AccessDenied` explicitly — don't retry indefinitely on authorization failures.

---

## Troubleshooting

| Error Type | Typical Cause | Action |
|------------|---------------|--------|
| `ClientError: AccessDenied` | IAM policy | Fix permissions; do not retry |
| `ClientError: Throttling` | Rate limit | Retry with backoff |
| `BotoCoreError: ConnectionError` | Network/VPC | Check endpoints, NAT, security groups |
| `ClientError: ValidationException` | Bad parameter | Fix input; do not retry |
| `Partial failures in batch ops` | Mixed permissions | Inspect `Errors` array in response |

---

## Best Practices

- Catch `ClientError` specifically — not bare `Exception`.
- Maintain a **retryable vs fatal** error code set per service.
- Include **context** (bucket, key, job name) in error logs.
- Use **`RequestId`** when opening AWS support cases.
- Propagate errors after logging — don't swallow exceptions silently.
- Test error paths with moto or localstack in unit tests.
