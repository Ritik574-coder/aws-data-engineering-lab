# IAM — Policies

## Service Overview

IAM policies are JSON documents defining Allow/Deny statements for AWS actions on resources.

---

## AWS CLI Commands

### Create Customer Managed Policy

```bash
aws iam create-policy \
  --policy-name DataLakeS3Access \
  --policy-document file://data-lake-policy.json
```

**Sample `data-lake-policy.json`:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListRawBucket",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::my-data-lake-raw",
      "Condition": {
        "StringLike": {"s3:prefix": ["orders/*", "customers/*"]}
      }
    },
    {
      "Sid": "ObjectAccess",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": [
        "arn:aws:s3:::my-data-lake-raw/orders/*",
        "arn:aws:s3:::my-data-lake-raw/customers/*"
      ]
    }
  ]
}
```

### Get Policy Version

```bash
aws iam get-policy-version \
  --policy-arn arn:aws:iam::123456789012:policy/DataLakeS3Access \
  --version-id v1
```

### Simulate Policy

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/GlueETLRole \
  --action-names glue:StartJobRun s3:GetObject \
  --resource-arns arn:aws:s3:::my-data-lake-raw/orders/*
```

---

## Advanced Commands

### Validate Policy

```bash
aws accessanalyzer validate-policy \
  --policy-document file://data-lake-policy.json \
  --policy-type IDENTITY_POLICY
```

### List Policy Tags

```bash
aws iam list-policy-tags \
  --policy-arn arn:aws:iam::123456789012:policy/DataLakeS3Access
```

---

## Python (Boto3) Examples

```python
import json
import boto3

iam = boto3.client("iam")

def create_policy(name: str, document: dict) -> str:
    response = iam.create_policy(
        PolicyName=name,
        PolicyDocument=json.dumps(document),
    )
    return response["Policy"]["Arn"]
```

---

## Security Considerations

- Avoid `"Action": "*"` and `"Resource": "*"` in production policies.
- Use **condition keys** (`aws:SourceIp`, `aws:PrincipalTag`, `s3:prefix`).
- Version policies in Git; use Infrastructure as Code (Terraform/CloudFormation).

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| Explicit Deny | Conflicting Deny statement | Search all attached policies for Deny |
| Policy too large | Exceeds size limit | Split into multiple policies or use ABAC |

---

## Best Practices

- Use **AWS managed policies** as baseline; customize with customer-managed policies.
- Run **IAM Access Analyzer** policy validation before deployment.
- Document required permissions per pipeline in README/runbooks.
