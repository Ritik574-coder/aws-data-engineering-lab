# Troubleshooting — Debugging AWS CLI

## Service Overview

The AWS CLI v2 provides built-in debugging tools to diagnose authentication, authorization, networking, and API request issues. This guide covers debug output, logging, request tracing, and systematic troubleshooting workflows for data engineering operations.

---

## AWS CLI Commands

### Enable Debug Output

```bash
aws s3 ls s3://my-data-lake-raw/ --debug 2>&1 | tee debug.log
```

**Key sections in debug output:**
| Section | What It Shows |
|---------|---------------|
| `Event choose-service-name` | Which AWS service is called |
| `Event before-call` | Request URL, headers, parameters |
| `Event request-created` | Full HTTP request details |
| `Event response-received` | HTTP status code, response headers |
| `Event needs-retry` | Retry attempts and reasons |
| `Looking for credentials` | Credential provider chain resolution |

### Filter Debug Output

```bash
# Credential resolution only
aws sts get-caller-identity --debug 2>&1 | grep -i credential

# HTTP requests only
aws s3 ls --debug 2>&1 | grep -E "Sending http|Response headers|status"

# Errors only
aws glue get-job --job-name orders-etl --debug 2>&1 | grep -iE "error|exception|denied|403|404"
```

### CLI Binary Debug (Lower Level)

```bash
AWS_CLI_FILE_DEBUG=1 aws s3 ls 2>&1 | head -50
```

---

### Query Mode for Response Inspection

```bash
aws s3api list-objects-v2 \
  --bucket my-data-lake-raw \
  --prefix orders/ \
  --max-keys 5 \
  --output json | python3 -m json.tool
```

Output formats: `json`, `yaml`, `text`, `table`

```bash
aws glue get-databases --output table
aws glue get-databases --query 'DatabaseList[*].Name' --output text
```

---

### Dry Run (S3)

```bash
aws s3 sync ./local-data s3://my-bucket/prefix/ --dryrun
```

---

### CLI Configuration Inspection

```bash
aws configure list
aws configure list-profiles
aws configure get region --profile data-engineer

# Full config file
cat ~/.aws/config
cat ~/.aws/credentials  # redact before sharing
```

---

## Advanced Commands

### Endpoint Override (Debug PrivateLink)

```bash
aws s3 ls \
  --endpoint-url https://bucket.vpce-abc123-s3.us-east-1.vpce.amazonaws.com \
  --debug
```

### Disable SSL Verification (Debug Only — Never Production)

```bash
aws s3 ls --no-verify-ssl --debug
```

### Request Presigned URL Debug

```bash
aws s3 presign s3://my-bucket/orders/data.parquet --expires-in 3600
curl -v "<presigned-url>" 2>&1 | head -30
```

### CLI Telemetry

```bash
AWS_CLI_METRICS=1 aws s3 ls
```

### Trace Specific API Call with Timestamp

```bash
date -u +"%Y-%m-%dT%H:%M:%SZ" && \
  aws cloudtrail lookup-events \
    --lookup-attributes AttributeKey=EventName,AttributeValue=GetObject \
    --max-results 5
```

Correlate CLI `RequestId` from debug output with CloudTrail events.

---

## Python Boto3 Examples

### Enable Botocore Debug Logging

```python
import logging
import boto3

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("botocore").setLevel(logging.DEBUG)
logging.getLogger("urllib3").setLevel(logging.DEBUG)

s3 = boto3.client("s3")
s3.list_buckets()
```

### Capture Request ID

```python
import boto3

s3 = boto3.client("s3")
response = s3.list_objects_v2(Bucket="my-bucket", MaxKeys=1)
request_id = response["ResponseMetadata"]["RequestId"]
print(f"RequestId: {request_id}")
```

Use RequestId when opening AWS Support cases or correlating with CloudTrail.

---

## Security Considerations

- **`--debug` output contains sensitive data** — authorization headers, presigned URLs, account IDs.
- Redact debug logs before sharing in Slack, tickets, or PRs.
- Never use `--no-verify-ssl` outside isolated test environments.
- Do not commit `~/.aws/credentials` or debug logs to version control.

---

## Troubleshooting

### Systematic Debug Workflow

```
1. aws sts get-caller-identity          → Auth OK?
2. aws configure list                 → Credential source?
3. aws <command> --debug 2>&1 | tee log → Full trace
4. Extract RequestId from output       → CloudTrail lookup
5. iam simulate-principal-policy       → Authz check
6. Fix and re-test without --debug
```

### Common Debug Findings

| Debug Signal | Meaning | Action |
|--------------|---------|--------|
| `Unable to locate credentials` | No creds in chain | Fix profile/SSO/env vars |
| `Refreshing credentials` then fail | Expired SSO token | `aws sso login` |
| `Received non 2xx response: 403` | Access denied | Check IAM/LF/bucket policy |
| `Received non 2xx response: 404` | Resource not found | Verify name and region |
| `ConnectionError` | Network issue | Check VPC endpoints, NAT, SG |
| `Retry needed` repeated | Throttling | Reduce rate; increase retry config |
| Wrong endpoint URL | Region mismatch | Set `--region` explicitly |

### Extract RequestId from Debug Log

```bash
grep -i request-id debug.log | tail -5
grep -i 'x-amzn-requestid' debug.log | tail -5
```

### CloudTrail Correlation

```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventSource,AttributeValue=s3.amazonaws.com \
  --start-time 2025-03-01T00:00:00Z \
  --max-results 10 \
  --query 'Events[*].[EventTime,EventName,Username,CloudTrailEvent]' \
  --output table
```

---

## Best Practices

- Use **`--debug`** as a last resort — it is verbose; start with error message and `simulate-principal-policy`.
- Save debug output to a file (`tee debug.log`) for complex issues requiring team review.
- Always capture **`RequestId`** — the fastest path to CloudTrail correlation.
- Test with **`--region` explicitly specified** to eliminate region ambiguity.
- Use **`--query` (JMESPath)** to isolate relevant response fields and reduce noise.
- Create **shell aliases** for common debug patterns:

```bash
alias awswho='aws sts get-caller-identity'
alias awsdebug='aws --debug 2>&1 | tee ~/aws-debug-$(date +%Y%m%d-%H%M%S).log'
```

- Remove `--debug` from CI/CD scripts — use structured logging and CloudTrail instead.
- Keep **AWS CLI v2 updated** — `aws --version`; bug fixes affect credential and retry behavior.
