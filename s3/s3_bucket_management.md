# S3 — Bucket Management

## Service Overview

Bucket management covers creating, configuring, tagging, and deleting S3 buckets — foundational setup for data lake zones.

**Common use cases:**
- Provisioning raw/curated/analytics bucket tiers
- Enabling versioning for audit trails
- Configuring cross-region replication for DR
- Applying tags for cost allocation

---

## AWS CLI Commands

### Create Bucket

```bash
# us-east-1 (no LocationConstraint)
aws s3api create-bucket --bucket my-data-lake-raw

# Other regions
aws s3api create-bucket \
  --bucket my-data-lake-raw-eu \
  --region eu-west-1 \
  --create-bucket-configuration LocationConstraint=eu-west-1
```

### Delete Empty Bucket

```bash
aws s3 rb s3://temp-etl-bucket --force
```

### Get Bucket Location

```bash
aws s3api get-bucket-location --bucket my-data-lake-raw
```

**Example Output:**

```json
{
    "LocationConstraint": "us-west-2"
}
```

### Tag Bucket

```bash
aws s3api put-bucket-tagging \
  --bucket my-data-lake-raw \
  --tagging 'TagSet=[{Key=Environment,Value=prod},{Key=DataZone,Value=raw}]'
```

### Enable Versioning

```bash
aws s3api put-bucket-versioning \
  --bucket my-data-lake-raw \
  --versioning-configuration Status=Enabled
```

### Block Public Access

```bash
aws s3api put-public-access-block \
  --bucket my-data-lake-raw \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

---

## Advanced Commands

### List Buckets with JMESPath Filter

```bash
aws s3api list-buckets \
  --query 'Buckets[?starts_with(Name, `data-`)].{Name:Name,Created:CreationDate}' \
  --output table
```

### Enable Request Metrics

```bash
aws s3api put-bucket-metrics-configuration \
  --bucket my-data-lake-raw \
  --id EntireBucket \
  --metrics-configuration '{"Id": "EntireBucket"}'
```

### Configure Event Notifications

```bash
aws s3api put-bucket-notification-configuration \
  --bucket my-data-lake-raw \
  --notification-configuration '{
    "LambdaFunctionConfigurations": [{
      "LambdaFunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:ingest-trigger",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {"Key": {"FilterRules": [{"Name": "prefix", "Value": "incoming/"}]}}
    }]
  }'
```

---

## Python (Boto3) Examples

### Create Bucket with Encryption and Public Access Block

```python
import boto3
from botocore.exceptions import ClientError

def create_data_lake_bucket(name: str, region: str) -> None:
    s3 = boto3.client("s3", region_name=region)
    try:
        if region == "us-east-1":
            s3.create_bucket(Bucket=name)
        else:
            s3.create_bucket(
                Bucket=name,
                CreateBucketConfiguration={"LocationConstraint": region},
            )

        s3.put_public_access_block(
            Bucket=name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
        s3.put_bucket_encryption(
            Bucket=name,
            ServerSideEncryptionConfiguration={
                "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "aws:kms"}}]
            },
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "BucketAlreadyOwnedByYou":
            raise
```

---

## Security Considerations

- Enable **Block Public Access** on all data buckets by default.
- Use **separate buckets** per environment (dev/staging/prod).
- Apply **bucket policies** denying unencrypted uploads.
- Enable **CloudTrail** S3 data events for sensitive buckets.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `BucketAlreadyExists` | Globally unique name taken | Choose a unique name with account suffix |
| `BucketNotEmpty` | Objects remain on delete | Empty bucket first with `aws s3 rm --recursive` |
| `IllegalLocationConstraintException` | Region mismatch | Match LocationConstraint to target region |

---

## Best Practices

- Naming convention: `{org}-{env}-{domain}-{region}` (e.g., `acme-prod-raw-us-east-1`).
- Enable **versioning** on curated/analytics zones; consider lifecycle for noncurrent versions.
- Use **S3 Access Points** for multi-team access with isolated policies.
- Document bucket purpose in **tags** and runbooks.
