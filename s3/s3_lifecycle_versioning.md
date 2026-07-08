# S3 — Lifecycle & Versioning

## Service Overview

Lifecycle policies automate transitions to cheaper storage classes and object expiration. Versioning preserves object history for audit and recovery.

**Common use cases:**
- Expire temp/staging prefixes after 7 days
- Transition raw logs to Glacier after 90 days
- Retain noncurrent versions for compliance

---

## AWS CLI Commands

### Put Lifecycle Configuration

```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket my-data-lake-raw \
  --lifecycle-configuration '{
    "Rules": [
      {
        "ID": "ExpireTempPrefix",
        "Status": "Enabled",
        "Filter": {"Prefix": "temp/"},
        "Expiration": {"Days": 7}
      },
      {
        "ID": "TransitionLogsToGlacier",
        "Status": "Enabled",
        "Filter": {"Prefix": "logs/"},
        "Transitions": [{"Days": 90, "StorageClass": "GLACIER_IR"}]
      },
      {
        "ID": "CleanupNoncurrentVersions",
        "Status": "Enabled",
        "Filter": {"Prefix": ""},
        "NoncurrentVersionExpiration": {"NoncurrentDays": 30}
      }
    ]
  }'
```

### Get Lifecycle Configuration

```bash
aws s3api get-bucket-lifecycle-configuration --bucket my-data-lake-raw
```

### Enable Versioning

```bash
aws s3api put-bucket-versioning \
  --bucket analytics-curated \
  --versioning-configuration Status=Enabled
```

### List Object Versions

```bash
aws s3api list-object-versions \
  --bucket analytics-curated \
  --prefix orders/dt=2025-03-01/
```

---

## Advanced Commands

### Abort Incomplete Multipart Uploads (Lifecycle)

```json
{
  "ID": "AbortIncompleteMultipart",
  "Status": "Enabled",
  "Filter": {"Prefix": ""},
  "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7}
}
```

### Intelligent-Tiering Configuration

```bash
aws s3api put-bucket-intelligent-tiering-configuration \
  --bucket my-data-lake-raw \
  --id EntireBucket \
  --intelligent-tiering-configuration '{
    "Id": "EntireBucket",
    "Status": "Enabled",
    "Tierings": [{"Days": 90, "AccessTier": "ARCHIVE_ACCESS"}]
  }'
```

---

## Python (Boto3) Examples

```python
import boto3

def apply_lifecycle(bucket: str) -> None:
    s3 = boto3.client("s3")
    s3.put_bucket_lifecycle_configuration(
        Bucket=bucket,
        LifecycleConfiguration={
            "Rules": [
                {
                    "ID": "ExpireStaging",
                    "Status": "Enabled",
                    "Filter": {"Prefix": "staging/"},
                    "Expiration": {"Days": 14},
                }
            ]
        },
    )
```

---

## Security Considerations

- Lifecycle deletes are **irreversible** — test rules on non-production buckets first.
- Versioning increases storage cost; pair with **NoncurrentVersionExpiration**.
- Glacier retrieval requires appropriate IAM permissions and may incur retrieval fees.

---

## Troubleshooting

| Issue | Root Cause | Resolution |
|-------|------------|------------|
| Objects not expiring | Rule prefix mismatch | Verify prefix filter matches object keys |
| Versioning suspended unexpectedly | Manual config change | Audit with AWS Config |
| High storage costs | Noncurrent versions accumulating | Add NoncurrentVersionExpiration rule |

---

## Best Practices

- Use **prefix-based rules** aligned with data zones (`temp/`, `raw/`, `archive/`).
- Enable **S3 Storage Lens** to validate lifecycle effectiveness.
- For analytics data accessed monthly, consider **Intelligent-Tiering**.
- Document retention requirements per dataset for compliance (GDPR, SOX).
