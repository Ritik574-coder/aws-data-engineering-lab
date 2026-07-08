# S3 — Security & Permissions

## Service Overview

S3 security combines IAM policies, bucket policies, ACLs, Block Public Access, encryption, and access points to protect data lake assets.

**When to use:** Always — before any production data lands in S3.

---

## AWS CLI Commands

### Get Bucket Policy

```bash
aws s3api get-bucket-policy --bucket my-data-lake-raw --output text
```

### Put Bucket Policy (Deny Unencrypted Uploads)

```bash
aws s3api put-bucket-policy --bucket my-data-lake-raw --policy '{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "DenyUnencryptedObjectUploads",
    "Effect": "Deny",
    "Principal": "*",
    "Action": "s3:PutObject",
    "Resource": "arn:aws:s3:::my-data-lake-raw/*",
    "Condition": {
      "StringNotEquals": {
        "s3:x-amz-server-side-encryption": "aws:kms"
      }
    }
  }]
}'
```

### Get Bucket Encryption

```bash
aws s3api get-bucket-encryption --bucket my-data-lake-raw
```

### Enable Default Encryption (KMS)

```bash
aws s3api put-bucket-encryption \
  --bucket my-data-lake-raw \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "aws:kms",
        "KMSMasterKeyID": "alias/data-lake-key"
      },
      "BucketKeyEnabled": true
    }]
  }'
```

### Get Public Access Block

```bash
aws s3api get-public-access-block --bucket my-data-lake-raw
```

---

## Advanced Commands

### IAM Policy Simulation

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/DataEngineer \
  --action-names s3:GetObject s3:PutObject \
  --resource-arns arn:aws:s3:::my-data-lake-raw/orders/*
```

### List Access Points

```bash
aws s3control list-access-points --account-id 123456789012
```

---

## Python (Boto3) Examples

### Verify Object Encryption

```python
import boto3

s3 = boto3.client("s3")
meta = s3.head_object(Bucket="my-data-lake-raw", Key="orders/file.parquet")
assert meta.get("ServerSideEncryption") == "aws:kms"
print("KMS Key:", meta.get("SSEKMSKeyId"))
```

### Least-Privilege Prefix Access (IAM Policy Document)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::my-data-lake-raw",
      "Condition": {
        "StringLike": {"s3:prefix": ["orders/*"]}
      }
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::my-data-lake-raw/orders/*"
    }
  ]
}
```

---

## Security Considerations

- Prefer **bucket policies + IAM roles** over long-lived access keys.
- Use **Lake Formation** or **S3 Access Points** for fine-grained multi-tenant access.
- Enable **Macie** for PII discovery in data lakes.
- Rotate KMS keys per compliance requirements; use **Bucket Key** to reduce KMS costs.
- Deny `s3:*` without TLS via `aws:SecureTransport` condition.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `AccessDenied` on ListBucket | Missing prefix condition | Add `s3:prefix` condition to ListBucket grant |
| KMS `AccessDeniedException` | Role lacks kms:Decrypt | Grant KMS key usage to IAM role |
| Public access despite private ACL | Block Public Access disabled | Enable account-level Block Public Access |

---

## Best Practices

- **Separate roles** per pipeline stage (ingest, transform, read-only analytics).
- Audit policies with **IAM Access Analyzer** and **S3 Storage Lens**.
- Use **Object Ownership = Bucket owner enforced** to disable ACLs.
- Require **SSE-KMS** for all production buckets.
