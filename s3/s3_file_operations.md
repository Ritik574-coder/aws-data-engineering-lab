# S3 — File Operations

## Service Overview

S3 file operations cover uploading, downloading, multipart transfers, presigned URLs, and object metadata management — the day-to-day tasks in data pipelines.

**Common use cases:**
- Landing raw files from external systems
- Moving curated datasets between zones (raw → curated → analytics)
- Generating presigned URLs for secure file sharing
- Multipart uploads for large files (>100 MB)

---

## AWS CLI Commands

### Upload Single File

```bash
aws s3 cp ./data/events.json s3://my-data-lake-raw/events/dt=2025-03-01/events.json
```

### Upload with Content Type

```bash
aws s3 cp ./report.csv s3://analytics-curated/reports/report.csv \
  --content-type text/csv
```

### Download Entire Prefix

```bash
aws s3 cp s3://my-data-lake-raw/orders/year=2025/ ./local-orders/ --recursive
```

### Move Objects (Copy + Delete)

```bash
aws s3 mv s3://etl-staging-bucket/processed/ s3://analytics-curated/orders/ --recursive
```

### Generate Presigned URL

**Purpose:** Temporary download link without making bucket public.

```bash
aws s3 presign s3://analytics-curated/sample.parquet --expires-in 3600
```

**Example Output:**

```
https://analytics-curated.s3.amazonaws.com/sample.parquet?X-Amz-Algorithm=...
```

---

### Head Object (Metadata)

```bash
aws s3api head-object \
  --bucket analytics-curated \
  --key orders/dt=2025-03-01/output.parquet
```

**Example Output (JSON):**

```json
{
    "ContentLength": 13107200,
    "ContentType": "binary/octet-stream",
    "ETag": "\"d41d8cd98f00b204e9800998ecf8427e\"",
    "Metadata": {
        "pipeline": "glue-job-orders"
    },
    "ServerSideEncryption": "aws:kms"
}
```

---

### Copy Object Within S3

```bash
aws s3api copy-object \
  --copy-source my-data-lake-raw/incoming/file.csv \
  --bucket analytics-curated \
  --key staging/file.csv \
  --server-side-encryption aws:kms \
  --ssekms-key-id alias/data-lake-key
```

---

## Advanced Commands

### Multipart Upload (Large Files)

```bash
# AWS CLI handles multipart automatically for large files
aws s3 cp ./large-dataset.parquet s3://my-data-lake-raw/large-dataset.parquet \
  --expected-size 5368709120
```

### Concurrent Transfers

```bash
aws configure set default.s3.max_concurrent_requests 20
aws configure set default.s3.multipart_threshold 64MB
aws configure set default.s3.multipart_chunksize 16MB
```

### Select Content (SQL on CSV/JSON)

```bash
aws s3api select-object-content \
  --bucket my-data-lake-raw \
  --key sales.csv \
  --expression "SELECT * FROM S3Object WHERE cast(_1 AS int) > 1000" \
  --expression-type SQL \
  --input-serialization '{"CSV": {"FileHeaderInfo": "USE"}}' \
  --output-serialization '{"CSV": {}}' \
  output.csv
```

### Checksum Validation

```bash
aws s3 cp ./file.parquet s3://analytics-curated/file.parquet --checksum-algorithm CRC32
```

---

## Python (Boto3) Examples

### Presigned URL Generation

```python
import boto3

s3 = boto3.client("s3")
url = s3.generate_presigned_url(
    "get_object",
    Params={"Bucket": "analytics-curated", "Key": "sample.parquet"},
    ExpiresIn=3600,
)
print(url)
```

### Production — Multipart Upload with Progress

```python
import logging
from pathlib import Path

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

CONFIG = TransferConfig(
    multipart_threshold=64 * 1024 * 1024,
    max_concurrent_requests=10,
    multipart_chunksize=16 * 1024 * 1024,
)


def upload_large_file(local_path: str, bucket: str, key: str) -> None:
    s3 = boto3.client("s3")
    path = Path(local_path)
    try:
        s3.upload_file(str(path), bucket, key, Config=CONFIG)
        logger.info("Multipart upload complete: s3://%s/%s", bucket, key)
    except ClientError:
        logger.exception("Multipart upload failed for %s", key)
        raise
```

---

## Security Considerations

- Presigned URLs should use **short expiry** (minutes to hours, not days).
- Restrict `s3:PutObject` with **condition keys** (`s3:x-amz-server-side-encryption`).
- Validate file types at ingestion; scan with Macie for sensitive data.
- Never embed long-lived credentials in presigned URL generation scripts — use IAM roles.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `EntityTooLarge` | Exceeds single PUT limit (5 GB) | Use multipart upload |
| `SignatureDoesNotMatch` | Clock skew or expired presigned URL | Sync NTP; regenerate URL |
| Incomplete multipart upload | Process interrupted | Run lifecycle rule to abort incomplete uploads |

---

## Best Practices

- Use **`aws s3 sync`** for directory-level operations in CI/CD pipelines.
- Set **Content-Type** correctly for browser and Athena compatibility.
- For files > 100 MB, tune **multipart settings** for your network.
- Archive with **S3 Inventory** for reconciliation jobs.
- Use **S3 Object Lambda** or **Lambda** triggers for lightweight transformations at ingress.
