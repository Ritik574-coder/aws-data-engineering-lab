# Boto3 — Retries

## Service Overview

Boto3 uses **botocore** retry logic to handle transient failures — throttling, service errors, and connection issues. Configuring retries correctly prevents pipeline failures on temporary AWS API issues while avoiding infinite loops on permanent errors.

**Retry modes:**
| Mode | Behavior |
|------|----------|
| `legacy` | Default in older botocore; exponential backoff |
| `standard` | Recommended; respects retry headers |
| `adaptive` | Standard + client-side rate limiting (best for high throughput) |

---

## AWS CLI Commands

Retry configuration in `~/.aws/config`:

```ini
[default]
retry_mode = adaptive
max_attempts = 10
```

Per-command override:

```bash
aws s3 cp s3://bucket/large-file.parquet /tmp/ --cli-read-timeout 300
```

Environment variables:

```bash
export AWS_RETRY_MODE=adaptive
export AWS_MAX_ATTEMPTS=10
```

---

## Advanced Commands

### Disable Retries (Debugging Only)

```bash
AWS_MAX_ATTEMPTS=1 aws dynamodb get-item --table-name test --key '{"id":{"S":"1"}}'
```

### CLI Read/Connect Timeouts

```bash
aws configure set cli_connect_timeout 10 --profile data-engineer
aws configure set cli_read_timeout 120 --profile data-engineer
```

---

## Python Boto3 Examples

### Config with Adaptive Retries

```python
import boto3
from botocore.config import Config

config = Config(
    retries={
        "max_attempts": 10,
        "mode": "adaptive",
    },
    connect_timeout=5,
    read_timeout=60,
)

s3 = boto3.client("s3", config=config)
```

### Per-Client Retry Configuration

```python
glue_config = Config(retries={"max_attempts": 15, "mode": "adaptive"})
athena_config = Config(retries={"max_attempts": 5, "mode": "standard"})

session = boto3.Session()
glue = session.client("glue", config=glue_config)
athena = session.client("athena", config=athena_config)
```

### Custom Retry with Tenacity

For application-level retries beyond botocore:

```python
import logging

import boto3
from botocore.exceptions import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

logger = logging.getLogger(__name__)

RETRYABLE = {"Throttling", "ThrottlingException", "SlowDown", "ServiceUnavailable"}


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, ClientError):
        return exc.response["Error"]["Code"] in RETRYABLE
    return False


@retry(
    retry=retry_if_exception(is_retryable),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    before_sleep=lambda rs: logger.warning("Retry attempt %d", rs.attempt_number),
)
def start_glue_job(glue_client, job_name: str, arguments: dict) -> str:
    response = glue_client.start_job_run(JobName=job_name, Arguments=arguments)
    return response["JobRunId"]
```

### No Retries (Fail Fast)

```python
from botocore.config import Config

config = Config(retries={"max_attempts": 1})
s3 = boto3.client("s3", config=config)
```

### Inspect Retry Attempts (Debug)

```python
from botocore.config import Config
from botocore.hooks import HierarchicalEmitter

# Enable botocore debug logging
import logging
logging.getLogger("botocore").setLevel(logging.DEBUG)
logging.getLogger("urllib3").setLevel(logging.DEBUG)

s3 = boto3.client("s3", config=Config(retries={"max_attempts": 3, "mode": "standard"}))
```

---

## Security Considerations

- Retrying `AccessDenied` wastes API calls — ensure retry logic excludes authorization errors.
- High `max_attempts` on mutating operations risks duplicate side effects — design idempotent operations.
- Adaptive mode may slow throughput intentionally — monitor pipeline SLAs.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Still throttled after retries | Increase `max_attempts`; use adaptive mode; reduce concurrency |
| Duplicate resources created | Make creates idempotent; use conditional writes |
| Long pipeline hangs | Set `read_timeout`; don't rely on infinite retries |
| Retries not working | Verify `Config` passed to `client()`, not `Session()` |
| `Connection reset` errors | Check VPC endpoints, NAT gateway, security groups |

---

## Best Practices

- Use **`adaptive` retry mode** for high-volume S3, DynamoDB, and Glue operations.
- Set **`max_attempts: 10`** as a starting point; tune per service based on observed throttling.
- Combine botocore retries with **application-level idempotency** for writes.
- Configure **`read_timeout`** for long-running operations (Athena queries, large S3 transfers).
- Do not retry **`ValidationException`**, **`AccessDenied`**, or **`ResourceNotFoundException`**.
- Log retry attempts at WARNING level for operational visibility.
- Use **S3 Transfer Config** for multipart upload retries separately from API retries.

```python
from boto3.s3.transfer import TransferConfig

transfer_config = TransferConfig(
    multipart_threshold=64 * 1024 * 1024,
    max_concurrency=10,
    multipart_chunksize=16 * 1024 * 1024,
    use_threads=True,
)
s3.upload_file("large.parquet", "bucket", "key", Config=transfer_config)
```
