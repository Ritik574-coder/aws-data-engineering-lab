# S3 — Basic Commands

## Service Overview

**Amazon S3 (Simple Storage Service)** is object storage built to store and retrieve any amount of data. It is the foundation of most AWS data engineering workloads.

**Common use cases:**
- Data lake storage (raw, curated, and analytics zones)
- ETL staging and landing zones
- Static asset hosting and log archival
- Backup and disaster recovery targets

**When to use it:** Any time you need durable, scalable object storage with fine-grained access control, lifecycle policies, and integration with Athena, Glue, Redshift Spectrum, and EMR.

---

## AWS CLI Commands

### List S3 Buckets

**Purpose:** List all S3 buckets in the current AWS account.

**Command:**

```bash
aws s3 ls
```

**Example Output:**

```
2025-01-15 10:30:00 my-data-lake-raw
2025-01-15 10:31:00 analytics-curated
2025-02-01 08:00:00 etl-staging-bucket
```

**Explanation:** Displays bucket name and creation date for every bucket accessible to the caller. Empty output means no buckets or insufficient permissions (`s3:ListAllMyBuckets`).

---

### List Objects in a Bucket

**Purpose:** List objects under a bucket prefix.

**Command:**

```bash
aws s3 ls s3://my-data-lake-raw/orders/ --human-readable --summarize
```

**Parameters:**
| Flag | Description |
|------|-------------|
| `--human-readable` | Show sizes in KB/MB/GB |
| `--summarize` | Print total object count and size |
| `--recursive` | List all objects under prefix |

**Example Output:**

```
2025-03-01 14:22:10   12.5 MiB orders/year=2025/month=03/day=01/part-00000.parquet
2025-03-01 14:22:11    8.2 MiB orders/year=2025/month=03/day=01/part-00001.parquet

Total Objects: 2
   Total Size: 20.7 MiB
```

---

### Copy Local File to S3

**Purpose:** Upload a file to S3 (common for pipeline outputs).

**Command:**

```bash
aws s3 cp ./output.parquet s3://analytics-curated/orders/dt=2025-03-01/output.parquet \
  --storage-class STANDARD_IA \
  --metadata pipeline=glue-job-orders,version=1.2
```

**Example Output:**

```
upload: ./output.parquet to s3://analytics-curated/orders/dt=2025-03-01/output.parquet
```

---

### Download from S3

**Purpose:** Download objects locally for validation or reprocessing.

**Command:**

```bash
aws s3 cp s3://my-data-lake-raw/sample.csv ./sample.csv
```

---

### Sync Directories

**Purpose:** Incremental sync between local and S3 (ETL artifact deployment).

**Command:**

```bash
aws s3 sync ./dist/ s3://etl-staging-bucket/jars/ --exclude "*.tmp" --delete
```

**Explanation:** Only uploads changed files. `--delete` removes S3 objects not present locally (use with caution in production).

---

### Remove Objects

**Purpose:** Delete one or more objects.

**Command:**

```bash
aws s3 rm s3://etl-staging-bucket/temp/run-id=abc123/ --recursive
```

---

## Advanced Commands

### JSON Output via API-Level Commands

```bash
aws s3api list-objects-v2 \
  --bucket my-data-lake-raw \
  --prefix orders/year=2025/ \
  --query 'Contents[].{Key:Key,Size:Size,Modified:LastModified}' \
  --output table
```

### Pagination

```bash
aws s3api list-objects-v2 \
  --bucket my-data-lake-raw \
  --prefix logs/ \
  --max-keys 1000 \
  --starting-token "eyJ..."
```

### Filter with JMESPath

```bash
aws s3api list-buckets \
  --query 'Buckets[?contains(Name, `data-lake`)].Name' \
  --output text
```

### Batch Delete

```bash
aws s3api delete-objects \
  --bucket etl-staging-bucket \
  --delete 'Objects=[{Key=temp/a.csv},{Key=temp/b.csv}]'
```

---

## Python (Boto3) Examples

### Basic — List Buckets

```python
import boto3

s3 = boto3.client("s3")
for bucket in s3.list_buckets()["Buckets"]:
    print(bucket["Name"], bucket["CreationDate"])
```

### Production-Ready — Upload with Metadata and Server-Side Encryption

```python
import logging
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def upload_parquet(local_path: str, bucket: str, key: str) -> None:
    s3 = boto3.client("s3")
    path = Path(local_path)
    if not path.exists():
        raise FileNotFoundError(local_path)

    try:
        s3.upload_file(
            str(path),
            bucket,
            key,
            ExtraArgs={
                "ServerSideEncryption": "aws:kms",
                "Metadata": {"source": "glue-etl", "format": "parquet"},
            },
        )
        logger.info("Uploaded s3://%s/%s (%s bytes)", bucket, key, path.stat().st_size)
    except ClientError as exc:
        logger.error("Upload failed: %s", exc.response["Error"]["Message"])
        raise
```

---

## Security Considerations

- Use **SSE-KMS** or **SSE-S3** for data at rest; prefer KMS for audit trails and key rotation.
- Apply **bucket policies** and **Block Public Access** at account and bucket level.
- Grant least-privilege IAM: `s3:GetObject`, `s3:PutObject`, `s3:ListBucket` scoped to specific prefixes.
- Enable **S3 access logging** or **CloudTrail data events** for sensitive buckets.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `AccessDenied` | Missing IAM or bucket policy | Verify policy allows action on bucket ARN and object ARN |
| `NoSuchBucket` | Wrong region or deleted bucket | Confirm bucket name; use correct regional endpoint |
| `SlowDown` | Request rate exceeded | Add prefix sharding; use S3 Transfer Acceleration or batch ops |
| `403 Forbidden` on public URL | Object is private | Use presigned URL or CloudFront with OAC |

---

## Best Practices

- **Partition data** by date (`year=/month=/day=`) for Athena and Glue performance.
- Use **lifecycle rules** to transition infrequent data to Glacier or expire temp prefixes.
- Prefer **Parquet/ORC** over CSV for analytics workloads.
- Use **`aws s3 sync`** with `--size-only` or checksums for large artifact deployments.
- Tag buckets for cost allocation (`Environment`, `Team`, `DataDomain`).
