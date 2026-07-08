# Boto3 — Best Practices

## Service Overview

This guide consolidates production patterns for using Boto3 in data engineering workloads — covering client configuration, resource management, testing, observability, and cost optimization.

---

## AWS CLI Commands

Boto3 best practices align with CLI configuration:

```bash
# Verify SDK and CLI use same profile/region
aws configure list --profile data-engineer
python -c "
import boto3
s = boto3.Session(profile_name='data-engineer')
print(s.region_name, s.get_credentials().method)
"
```

---

## Advanced Commands

### Enable CLI Telemetry (SDK Metrics)

```bash
export AWS_SDK_METRICS=1
aws s3 ls
```

### Validate IAM Permissions Before Deployment

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/GlueETLRole \
  --action-names s3:GetObject s3:PutObject glue:StartJobRun \
  --resource-arns arn:aws:s3:::my-data-lake-raw/* arn:aws:glue:us-east-1:123456789012:job/orders-etl
```

---

## Python Boto3 Examples

### Recommended Client Factory

```python
import boto3
from botocore.config import Config
from functools import lru_cache

DEFAULT_CONFIG = Config(
    retries={"max_attempts": 10, "mode": "adaptive"},
    connect_timeout=5,
    read_timeout=120,
    max_pool_connections=50,
)


@lru_cache(maxsize=None)
def get_client(service: str, region: str = "us-east-1", profile: str | None = None):
    session = boto3.Session(profile_name=profile, region_name=region)
    return session.client(service, config=DEFAULT_CONFIG)
```

### Structured Logging with Request ID

```python
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def call_with_logging(client, operation: str, **kwargs):
    method = getattr(client, operation)
    try:
        response = method(**kwargs)
        request_id = response["ResponseMetadata"]["RequestId"]
        logger.info("AWS %s.%s succeeded request_id=%s", client.meta.service_model.service_name, operation, request_id)
        return response
    except ClientError as exc:
        request_id = exc.response["ResponseMetadata"].get("RequestId", "N/A")
        logger.error(
            "AWS %s.%s failed code=%s request_id=%s",
            client.meta.service_model.service_name,
            operation,
            exc.response["Error"]["Code"],
            request_id,
        )
        raise
```

### Type Hints and Protocol

```python
from typing import Protocol, Any


class S3Client(Protocol):
    def put_object(self, **kwargs: Any) -> dict: ...
    def get_object(self, **kwargs: Any) -> dict: ...


def upload_report(s3: S3Client, bucket: str, key: str, data: bytes) -> None:
    s3.put_object(Bucket=bucket, Key=key, Body=data, ServerSideEncryption="aws:kms")
```

### Testing with moto

```python
import boto3
import pytest
from moto import mock_aws


@mock_aws
def test_upload():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-bucket")
    s3.put_object(Bucket="test-bucket", Key="test.txt", Body=b"data")
    resp = s3.get_object(Bucket="test-bucket", Key="test.txt")
    assert resp["Body"].read() == b"data"
```

---

## Security Considerations

- Use IAM roles in compute environments — never distribute access keys.
- Apply least-privilege policies scoped to resource ARNs and prefixes.
- Enable SSE-KMS for all S3 writes in data pipelines.
- Sanitize logs — never log object contents, credentials, or secrets.
- Use VPC endpoints for private AWS API access from data subnets.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Slow pipeline | Default connection pool too small | Increase `max_pool_connections` |
| Memory growth | Creating clients per call | Reuse session and clients |
| Intermittent failures | No retry config | Set adaptive retries |
| Wrong region errors | Implicit region | Pass `region_name` explicitly |
| Credential expiry mid-job | Long-running process | Use refreshable credentials |

---

## Best Practices

### Configuration
- Create **one Session per process**; reuse clients across calls.
- Pass **`Config`** with retries, timeouts, and pool size to every client.
- Set **region explicitly** — never assume a default.

### Performance
- Use **paginators** for all list operations.
- Use **S3 Transfer Manager** (`upload_file`, `download_file`) for large files.
- Batch operations where APIs support it (`delete_objects`, DynamoDB `batch_write_item`).
- Use **async** (aioboto3) only when I/O-bound concurrency is proven necessary.

### Reliability
- Design **idempotent** writes — use conditional checks and deterministic keys.
- Distinguish **retryable vs fatal** errors (see [error_handling.md](error_handling.md)).
- Set **timeouts** on all clients — pipelines should fail fast, not hang.

### Observability
- Log **`RequestId`** on every error.
- Emit **CloudWatch metrics** from pipeline code for business KPIs.
- Call **`get_caller_identity()`** at job start for audit trail.

### Testing
- Use **moto** or **localstack** for unit tests.
- Inject clients via **dependency injection** for testability.
- Run **IAM policy simulator** before deploying new pipeline permissions.

### Cost
- Scope S3 listings with **prefixes** matching partition structure.
- Avoid unnecessary `head_object` calls in loops — cache metadata.
- Use **Intelligent-Tiering** and lifecycle policies via IaC.

### Dependencies
- Pin **`boto3`** and **`botocore`** versions in `requirements.txt`.
- Test upgrades in staging — AWS adds new API parameters frequently.
- Monitor [Boto3 changelog](https://github.com/boto/boto3/blob/develop/CHANGELOG.rst) for breaking changes.
