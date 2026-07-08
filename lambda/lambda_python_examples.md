# Lambda — Python Boto3 Examples

## Service Overview

Boto3's `lambda` client supports deployment automation, operational tooling, and building control-plane services that orchestrate data pipelines. Combined with `boto3` clients for S3, Glue, and Athena, Lambda handlers form the glue layer of event-driven data architectures.

**Common use cases:**
- S3 event handlers that validate files and trigger Glue jobs
- Scheduled partition maintenance via EventBridge-triggered Lambda
- Internal APIs that kick off Athena data quality queries
- CI/CD scripts that deploy and smoke-test functions

**When to use it:** For automation outside Lambda itself (deploy scripts, ops runbooks) and for patterns that mirror what runs inside the handler.

---

## AWS CLI Commands

### Get Function ARN for Boto3 Automation

**Purpose:** Retrieve ARN for event source mapping or IAM policies.

**Command:**

```bash
aws lambda get-function \
  --function-name s3-landing-validator \
  --query 'Configuration.FunctionArn' \
  --output text
```

**Example Output:**

```
arn:aws:lambda:us-east-1:123456789012:function:s3-landing-validator
```

---

### Dry-Run Invoke with Log Tail

**Purpose:** Test handler and view logs inline.

**Command:**

```bash
aws lambda invoke \
  --function-name s3-landing-validator \
  --payload '{"dt": "2025-03-01"}' \
  --cli-binary-format raw-in-base64-out \
  --log-type Tail \
  response.json \
  | jq -r '.LogResult' | base64 -d
```

---

## Advanced Commands

### List Layers Used by Function

```bash
aws lambda get-function-configuration \
  --function-name s3-landing-validator \
  --query 'Layers[].Arn' \
  --output text
```

### Update Event Source Mapping Batch Size

```bash
aws lambda update-event-source-mapping \
  --uuid a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  --batch-size 25 \
  --maximum-batching-window-in-seconds 10
```

---

## Python Boto3 Examples

### S3 Event Handler — Validate and Trigger Glue

```python
import json
import logging
import os
import urllib.parse

import boto3

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

glue = boto3.client("glue")
s3 = boto3.client("s3")


def lambda_handler(event, context):
    glue_job = os.environ["GLUE_JOB_NAME"]

    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        logger.info("Processing s3://%s/%s", bucket, key)

        if not key.endswith(".parquet"):
            logger.warning("Skipping non-parquet file: %s", key)
            continue

        head = s3.head_object(Bucket=bucket, Key=key)
        size = head["ContentLength"]
        if size == 0:
            raise ValueError(f"Empty file: {key}")

        dt = _extract_partition(key, "dt")
        run_id = glue.start_job_run(
            JobName=glue_job,
            Arguments={"--source_bucket": bucket, "--source_key": key, "--dt": dt},
        )["JobRunId"]
        logger.info("Started Glue job %s run %s for dt=%s", glue_job, run_id, dt)

    return {"statusCode": 200, "body": json.dumps({"processed": len(event.get("Records", []))})}


def _extract_partition(key: str, partition_key: str) -> str:
    for part in key.split("/"):
        if part.startswith(f"{partition_key}="):
            return part.split("=", 1)[1]
    return "unknown"
```

### SQS Batch Handler with Partial Failure Reporting

```python
import json
import logging

import boto3

logger = logging.getLogger(__name__)
athena = boto3.client("athena")


def lambda_handler(event, context):
    failures = []

    for record in event.get("Records", []):
        message_id = record["messageId"]
        try:
            body = json.loads(record["body"])
            _run_dq_query(body["database"], body["sql"], body["output_location"])
        except Exception as exc:
            logger.exception("Failed message %s: %s", message_id, exc)
            failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failures}


def _run_dq_query(database: str, sql: str, output_location: str) -> None:
    qid = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": database},
        ResultConfiguration={"OutputLocation": output_location},
    )["QueryExecutionId"]
    waiter = athena.get_waiter("query_succeeded")
    waiter.wait(QueryExecutionId=qid, WaiterConfig={"Delay": 2, "MaxAttempts": 60})
```

### Production-Ready — Lambda Manager Class

```python
import json
import logging
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class InvokeResult:
    status_code: int
    payload: dict[str, Any]
    function_error: str | None


class LambdaManager:
    def __init__(self, region: str = "us-east-1"):
        self.client = boto3.client("lambda", region_name=region)

    def invoke_sync(self, function_name: str, payload: dict) -> InvokeResult:
        try:
            resp = self.client.invoke(
                FunctionName=function_name,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload),
            )
            raw = resp["Payload"].read()
            parsed = json.loads(raw) if raw else {}
            return InvokeResult(
                status_code=resp["StatusCode"],
                payload=parsed,
                function_error=resp.get("FunctionError"),
            )
        except ClientError as exc:
            logger.error("Invoke error: %s", exc.response["Error"]["Message"])
            raise

    def smoke_test(self, function_name: str, test_payload: dict) -> None:
        result = self.invoke_sync(function_name, test_payload)
        if result.function_error:
            raise RuntimeError(f"Function error: {result.function_error} — {result.payload}")
        logger.info("Smoke test passed for %s: %s", function_name, result.payload)
```

### Scheduled Partition Registration

```python
import os
from datetime import datetime, timedelta, timezone

import boto3


def lambda_handler(event, context):
    glue = boto3.client("glue")
    database = os.environ["GLUE_DATABASE"]
    table = os.environ["GLUE_TABLE"]
    s3_base = os.environ["S3_BASE_PATH"]

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    location = f"{s3_base.rstrip('/')}/dt={yesterday}/"

    try:
        glue.create_partition(
            DatabaseName=database,
            TableName=table,
            PartitionInput={
                "Values": [yesterday],
                "StorageDescriptor": {
                    "Location": location,
                    "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
                    "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
                    "SerdeInfo": {
                        "SerializationLibrary": "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
                    },
                },
            },
        )
        return {"created": True, "dt": yesterday}
    except glue.exceptions.AlreadyExistsException:
        return {"created": False, "dt": yesterday}
```

### Deploy Script Integration Test

```python
import boto3


def post_deploy_verify(function_name: str) -> None:
    lam = boto3.client("lambda")
    lam.get_waiter("function_active").wait(FunctionName=function_name)

    resp = lam.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=b'{"healthcheck": true}',
    )
    assert resp["StatusCode"] == 200
    assert resp.get("FunctionError") is None
```

---

## Security Considerations

- Load secrets in the handler via **Secrets Manager** (`get_secret_value`), not environment variables, for DB passwords and API keys.
- Validate and normalize **S3 keys** from events (`urllib.parse.unquote_plus`) to prevent path traversal confusion.
- Use **`ReportBatchItemFailures`** for SQS to avoid reprocessing entire batches on partial failure.
- Restrict Lambda **execution roles** to minimum S3 prefixes and specific Glue job names.
- Enable **X-Ray** tracing for production pipeline functions to audit downstream calls.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `ClientError: AccessDenied` on Glue | Execution role missing `glue:StartJobRun` | Update role policy with job ARN scope |
| SQS messages reprocessed endlessly | No partial batch failure reporting | Return `batchItemFailures` for failed items |
| `json.loads` fails on payload | Double-encoded JSON from SQS | Parse once; handle string vs dict bodies |
| Cold start timeout | Large imports at module level | Lazy-import heavy libs; use provisioned concurrency |
| Athena waiter timeout in Lambda | Query too long for Lambda timeout | Increase Lambda timeout or invoke Glue async instead |

---

## Best Practices

- Structure handlers as **`lambda_handler` → service functions** for unit testing without AWS.
- Use **environment variables** for configuration; **Secrets Manager** for credentials.
- Implement **idempotency** using S3 ETag or DynamoDB conditional writes for event deduplication.
- Log **`context.aws_request_id`** and **`context.function_name`** in structured JSON.
- Keep handler execution under **30 seconds** when possible; offload heavy work to Glue/Step Functions.
- Use **SQS + DLQ** instead of synchronous chains for reliability.
- Bundle only required dependencies; share heavy libs via **layers** or **container images**.
- Write **integration tests** that invoke deployed functions with realistic S3/SQS event fixtures.
