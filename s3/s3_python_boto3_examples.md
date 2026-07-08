# S3 — Python Boto3 Examples

## Service Overview

Boto3 is the AWS SDK for Python. The `s3` client and `S3` resource provide programmatic access to all S3 operations used in data pipelines.

---

## Basic Examples

### Session and Client

```python
import boto3

session = boto3.Session(profile_name="data-engineer", region_name="us-east-1")
s3 = session.client("s3")
resource = session.resource("s3")
```

### List and Paginate Objects

```python
paginator = s3.get_paginator("list_objects_v2")
for page in paginator.paginate(Bucket="my-data-lake-raw", Prefix="orders/"):
    for obj in page.get("Contents", []):
        print(obj["Key"], obj["Size"])
```

---

## Production-Ready Examples

### Idempotent Upload with Retry

```python
import logging
from botocore.config import Config

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

config = Config(retries={"max_attempts": 10, "mode": "adaptive"})
s3 = boto3.client("s3", config=config)


def put_object_if_not_exists(bucket: str, key: str, body: bytes) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        logger.info("Object already exists: s3://%s/%s", bucket, key)
        return False
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "404":
            raise

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ServerSideEncryption="aws:kms",
    )
    return True
```

### S3 Event Handler (Lambda-style)

```python
def process_s3_event(event: dict) -> None:
    s3 = boto3.client("s3")
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]
        logger.info("Processing s3://%s/%s", bucket, key)
        # Trigger downstream ETL
```

---

## Error Handling

```python
from botocore.exceptions import ClientError, BotoCoreError

try:
    s3.download_file("my-bucket", "missing.key", "/tmp/file")
except ClientError as exc:
    code = exc.response["Error"]["Code"]
    if code == "404":
        print("Object not found")
    elif code == "403":
        print("Access denied — check IAM policy")
    else:
        raise
except BotoCoreError:
    logger.exception("Network or credential error")
    raise
```

---

## Best Practices

- Use **`TransferConfig`** for large file uploads/downloads.
- Prefer **`get_paginator`** over manual pagination loops.
- Inject **`boto3.Session`** for testability (moto, localstack).
- Enable **adaptive retries** in `botocore.config.Config`.
- Log **request IDs** from `ClientError.response["ResponseMetadata"]` for AWS support.

---

## Troubleshooting

| Error | Resolution |
|-------|------------|
| `NoCredentialsError` | Configure profile, env vars, or IAM role |
| `EndpointConnectionError` | Check VPC endpoints or network path |
| `SlowDown` | Implement exponential backoff; reduce concurrency |
