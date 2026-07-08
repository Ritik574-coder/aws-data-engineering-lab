# Lambda — Management

## Service Overview

**AWS Lambda** runs event-driven code without managing servers. In data engineering, Lambda handles lightweight transforms, S3 event triggers, API ingestion endpoints, catalog automation, and orchestration glue between S3, Glue, Athena, and SNS/SQS.

**Common use cases:**
- Process S3 `ObjectCreated` events to trigger downstream ETL
- Lightweight file format validation before Glue jobs run
- Scheduled partition registration or Athena MSCK repair
- Fan-out notifications when pipeline stages complete

**When to use it:** For short-running (< 15 min), event-driven tasks. Prefer Glue/EMR for heavy Spark transforms; use Lambda for control plane and small I/O operations.

---

## AWS CLI Commands

### List Functions

**Purpose:** Enumerate Lambda functions in the account/region.

**Command:**

```bash
aws lambda list-functions --max-items 50
```

**Example Output (abbreviated):**

```json
{
    "Functions": [
        {
            "FunctionName": "s3-landing-validator",
            "Runtime": "python3.12",
            "Handler": "handler.lambda_handler",
            "Timeout": 60,
            "MemorySize": 256,
            "LastModified": "2025-02-15T10:00:00.000+0000"
        }
    ]
}
```

---

### Get Function Configuration

**Purpose:** Inspect runtime, role, environment variables, and concurrency settings.

**Command:**

```bash
aws lambda get-function-configuration --function-name s3-landing-validator
```

**Example Output (abbreviated):**

```json
{
    "FunctionName": "s3-landing-validator",
    "Runtime": "python3.12",
    "Role": "arn:aws:iam::123456789012:role/LambdaS3ValidatorRole",
    "Handler": "handler.lambda_handler",
    "Timeout": 60,
    "MemorySize": 256,
    "Environment": {
        "Variables": {
            "TARGET_BUCKET": "analytics-curated",
            "LOG_LEVEL": "INFO"
        }
    },
    "EphemeralStorage": {"Size": 512},
    "Architectures": ["x86_64"]
}
```

---

### Invoke Function (Test)

**Purpose:** Synchronously invoke a function with a test payload.

**Command:**

```bash
aws lambda invoke \
  --function-name s3-landing-validator \
  --payload '{"Records":[{"s3":{"bucket":{"name":"my-data-lake-raw"},"object":{"key":"orders/dt=2025-03-01/part-00000.parquet"}}}]}' \
  --cli-binary-format raw-in-base64-out \
  response.json

cat response.json
```

**Example Output:**

```json
{
    "StatusCode": 200,
    "ExecutedVersion": "$LATEST"
}
```

**response.json:**

```json
{"status": "valid", "rows_checked": 1000, "key": "orders/dt=2025-03-01/part-00000.parquet"}
```

---

### Update Function Configuration

**Purpose:** Change timeout, memory, or environment variables.

**Command:**

```bash
aws lambda update-function-configuration \
  --function-name s3-landing-validator \
  --timeout 120 \
  --memory-size 512 \
  --environment 'Variables={TARGET_BUCKET=analytics-curated,LOG_LEVEL=DEBUG}'
```

---

### List Event Source Mappings

**Purpose:** View SQS/Kinesis/DynamoDB triggers attached to a function.

**Command:**

```bash
aws lambda list-event-source-mappings --function-name s3-landing-validator
```

**Example Output (abbreviated):**

```json
{
    "EventSourceMappings": [
        {
            "UUID": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "EventSourceArn": "arn:aws:sqs:us-east-1:123456789012:landing-file-queue",
            "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:s3-landing-validator",
            "State": "Enabled",
            "BatchSize": 10
        }
    ]
}
```

---

### Put Function Concurrency

**Purpose:** Reserve or limit concurrent executions (protect downstream systems).

**Command:**

```bash
aws lambda put-function-concurrency \
  --function-name s3-landing-validator \
  --reserved-concurrent-executions 10
```

---

### Add Permission (S3 Invoke)

**Purpose:** Allow S3 to invoke Lambda (required for bucket notifications).

**Command:**

```bash
aws lambda add-permission \
  --function-name s3-landing-validator \
  --statement-id s3-invoke-permission \
  --action lambda:InvokeFunction \
  --principal s3.amazonaws.com \
  --source-arn arn:aws:s3:::my-data-lake-raw \
  --source-account 123456789012
```

---

### Tag Function

**Purpose:** Apply cost and ownership tags.

**Command:**

```bash
aws lambda tag-resource \
  --resource arn:aws:lambda:us-east-1:123456789012:function:s3-landing-validator \
  --tags Environment=prod,Team=data-platform,Pipeline=orders-ingest
```

---

### Delete Function

**Purpose:** Remove an unused function.

**Command:**

```bash
aws lambda delete-function --function-name old-test-validator
```

---

## Advanced Commands

### Publish Version

```bash
aws lambda publish-version --function-name s3-landing-validator
```

### Create Alias for Blue/Green

```bash
aws lambda create-alias \
  --function-name s3-landing-validator \
  --name prod \
  --function-version 3
```

### Filter Functions by Tag

```bash
aws lambda list-functions \
  --query 'Functions[?contains(FunctionName, `validator`)].{Name:FunctionName,Runtime:Runtime,Memory:MemorySize}' \
  --output table
```

### Get Function Policy

```bash
aws lambda get-policy --function-name s3-landing-validator
```

---

## Python Boto3 Examples

### Basic — Invoke Lambda

```python
import json

import boto3

lambda_client = boto3.client("lambda")

payload = {"dt": "2025-03-01", "action": "validate"}
response = lambda_client.invoke(
    FunctionName="s3-landing-validator",
    InvocationType="RequestResponse",
    Payload=json.dumps(payload),
)
result = json.loads(response["Payload"].read())
print(result)
```

### Production-Ready — Async Invoke with Error Handling

```python
import json
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def invoke_async(function_name: str, payload: dict) -> str:
    client = boto3.client("lambda")
    try:
        response = client.invoke(
            FunctionName=function_name,
            InvocationType="Event",
            Payload=json.dumps(payload),
        )
        status = response["StatusCode"]
        if status != 202:
            raise RuntimeError(f"Unexpected status {status}")
        logger.info("Async invoke accepted for %s", function_name)
        return response.get("ResponseMetadata", {}).get("RequestId", "")
    except ClientError as exc:
        logger.error("Invoke failed: %s", exc.response["Error"]["Message"])
        raise
```

### Update Environment Variables Idempotently

```python
import boto3


def set_env_var(function_name: str, key: str, value: str) -> None:
    lam = boto3.client("lambda")
    config = lam.get_function_configuration(FunctionName=function_name)
    env_vars = config.get("Environment", {}).get("Variables", {})
    env_vars[key] = value
    lam.update_function_configuration(
        FunctionName=function_name,
        Environment={"Variables": env_vars},
    )
```

---

## Security Considerations

- Attach **least-privilege IAM roles** per function — scope S3, Glue, and Athena actions to required prefixes.
- Avoid secrets in **environment variables**; use **Secrets Manager** or **SSM Parameter Store** with encryption.
- Enable **AWS Lambda Function URLs** only with IAM auth unless explicitly public-facing.
- Review **resource-based policies** (`get-policy`) for overly broad `Principal: *`.
- Enable **VPC** only when accessing private resources; understand ENI cold-start impact.
- Turn on **CloudWatch Logs** encryption with KMS for functions handling sensitive data.

---

## Troubleshooting

| Error / Symptom | Root Cause | Resolution |
|-----------------|------------|------------|
| `AccessDeniedException` on invoke | Missing `lambda:InvokeFunction` | Update caller IAM policy |
| `Task timed out` | Insufficient timeout or slow I/O | Increase timeout; optimize code; use async |
| `Runtime.ImportModuleError` | Missing dependency layer | Add Lambda layer or bundle deps in deployment package |
| S3 not triggering Lambda | Missing permission or notification | Run `add-permission`; configure bucket notification |
| `TooManyRequestsException` | Concurrency limit | Raise reserved concurrency or implement backoff |
| `HTTP 502` on invoke | Unhandled exception in handler | Check `/aws/lambda/<name>` CloudWatch log group |

---

## Best Practices

- Right-size **memory** (affects CPU proportionally); start at 256–512 MB for I/O-bound data tasks.
- Use **reserved concurrency** to protect downstream databases and APIs from overload.
- Prefer **SQS event source** over direct S3 invoke for buffering and DLQ support.
- Version functions with **aliases** (`prod`, `staging`) pointing to published versions.
- Keep handlers **thin** — delegate logic to testable modules in the deployment package.
- Set **`LOG_LEVEL`** via environment variable; structured JSON logging for observability.
- Tag all functions with `Environment`, `Team`, and `Pipeline` for cost allocation.
- Monitor **Errors**, **Duration**, and **Throttles** metrics with CloudWatch alarms.
