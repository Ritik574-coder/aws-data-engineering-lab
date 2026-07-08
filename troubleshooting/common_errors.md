# Troubleshooting — Common AWS Errors

## Service Overview

This reference covers frequently encountered AWS errors in data engineering workflows — across S3, Glue, Athena, IAM, and networking. Use it as a first-response guide before deep-diving into service-specific docs.

---

## AWS CLI Commands

### Quick Diagnostic Commands

```bash
# Who am I?
aws sts get-caller-identity

# What region am I using?
aws configure get region

# Test basic S3 access
aws s3 ls s3://my-data-lake-raw/ --region us-east-1

# Verbose debug output
aws s3 ls s3://my-bucket/ --debug 2>&1 | tail -100
```

---

## Advanced Commands

### Simulate IAM Permission

```bash
aws iam simulate-principal-policy \
  --policy-source-arn $(aws sts get-caller-identity --query Arn --output text) \
  --action-names s3:GetObject glue:StartJobRun \
  --resource-arns arn:aws:s3:::my-bucket/* arn:aws:glue:us-east-1:123456789012:job/my-job
```

### Check Service Quotas

```bash
aws service-quotas get-service-quota \
  --service-code glue \
  --quota-code L-2E7BCD9F
```

---

## Python Boto3 Examples

### Universal Error Inspector

```python
from botocore.exceptions import ClientError


def describe_error(exc: ClientError) -> dict:
    err = exc.response["Error"]
    meta = exc.response.get("ResponseMetadata", {})
    return {
        "code": err.get("Code"),
        "message": err.get("Message"),
        "http_status": meta.get("HTTPStatusCode"),
        "request_id": meta.get("RequestId"),
        "service": exc.operation_name,
    }
```

---

## Security Considerations

- Error messages may reveal resource names and account structure — sanitize before sharing externally.
- Do not paste full `--debug` output in tickets — may contain authorization headers.

---

## Troubleshooting

### S3 Errors

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `NoSuchBucket` | Wrong name, region, or deleted bucket | Verify bucket exists: `aws s3api head-bucket --bucket <name>` |
| `NoSuchKey` | Object path incorrect | List prefix: `aws s3 ls s3://bucket/prefix/` |
| `AccessDenied` | IAM or bucket policy | Check IAM policy, bucket policy, Block Public Access, SCP |
| `SlowDown` | Request rate exceeded | Add prefix sharding; reduce LIST frequency |
| `InvalidAccessKeyId` | Bad or rotated credentials | Refresh credentials; verify `AWS_PROFILE` |

### Glue / Athena Errors

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `EntityNotFoundException` | Database/table/job missing | Verify in Glue catalog; check region |
| `ConcurrentRunsExceededException` | Job concurrency limit | Wait or increase max concurrent runs |
| `AccessDeniedException` (Athena) | Missing LF or IAM permissions | Grant Lake Formation SELECT + DESCRIBE |
| `HIVE_CURSOR_ERROR` | Corrupt or misformatted data | Validate Parquet schema; check partition columns |
| `Query exhausted resources` | Query too large | Partition pruning; reduce scanned data |

### General API Errors

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `ThrottlingException` | API rate limit | Retry with backoff; request quota increase |
| `ValidationException` | Invalid parameter | Check API docs for required fields and formats |
| `ResourceNotFoundException` | ARN incorrect or wrong region | Verify ARN components and region |
| `LimitExceededException` | Account quota reached | Check Service Quotas; delete unused resources |
| `InternalServerError` | Transient AWS issue | Retry; check AWS Health Dashboard |

### Networking Errors

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `Could not connect to endpoint` | No internet or VPC endpoint | Configure NAT gateway or VPC endpoints |
| `Connection timed out` | Security group or NACL block | Verify SG rules for HTTPS (443) egress |
| `SSL validation failed` | Proxy or outdated CA bundle | Update CA certs; check corporate proxy |

---

## Best Practices

- Start every investigation with **`aws sts get-caller-identity`** — confirms account, role, and credentials.
- Check **region** explicitly — most "resource not found" errors are wrong-region issues.
- Use **`--debug`** sparingly for HTTP-level traces; redact sensitive output.
- Keep a **runbook** linking error codes to team-specific resources (bucket names, job names).
- Monitor **AWS Health Dashboard** and **Service Quotas** proactively.
- Enable **CloudTrail** and **CloudWatch Logs** for correlation when errors are intermittent.
