# CloudWatch — Logs

## Service Overview

**Amazon CloudWatch Logs** centralizes log streams from Lambda, Glue, ECS, and custom applications. Data engineers rely on it for debugging failed ETL runs, auditing pipeline behavior, and creating metric filters for error alerting.

**Common use cases:**
- Tail Glue driver and executor logs during job failures
- Search Lambda handler logs for S3 event processing errors
- Metric filters on `ERROR` patterns to trigger SNS alerts
- Log retention and archival to S3 for compliance

**When to use it:** Whenever a pipeline component emits stdout/stderr — CloudWatch Logs is the first stop for incident investigation.

---

## AWS CLI Commands

### Describe Log Groups

**Purpose:** List log groups and retention settings.

**Command:**

```bash
aws logs describe-log-groups \
  --log-group-name-prefix /aws/lambda/ \
  --max-items 20
```

**Example Output (abbreviated):**

```json
{
    "logGroups": [
        {
            "logGroupName": "/aws/lambda/s3-landing-validator",
            "retentionInDays": 30,
            "storedBytes": 52428800,
            "creationTime": 1708000000000
        },
        {
            "logGroupName": "/aws-glue/jobs/output",
            "retentionInDays": 14,
            "storedBytes": 1073741824
        }
    ]
}
```

---

### Tail Logs (Live)

**Purpose:** Follow log events in real time during debugging.

**Command:**

```bash
aws logs tail /aws/lambda/s3-landing-validator --follow --since 1h
```

**Example Output:**

```
2025-03-01T06:00:12.123000+00:00 START RequestId: abc-123 Version: $LATEST
2025-03-01T06:00:12.456000+00:00 Processing s3://my-data-lake-raw/orders/dt=2025-03-01/part-00000.parquet
2025-03-01T06:00:13.789000+00:00 Started Glue job orders-daily-etl run jr_xyz789
2025-03-01T06:00:13.890000+00:00 END RequestId: abc-123
2025-03-01T06:00:13.890000+00:00 REPORT RequestId: abc-123 Duration: 767.23 ms
```

---

### Filter Log Events

**Purpose:** Search logs for errors or specific patterns.

**Command:**

```bash
aws logs filter-log-events \
  --log-group-name /aws-glue/jobs/output \
  --filter-pattern "ERROR" \
  --start-time $(date -d '24 hours ago' +%s000) \
  --limit 50
```

**Example Output (abbreviated):**

```json
{
    "events": [
        {
            "logStreamName": "jr_a1b2c3d4",
            "timestamp": 1709289612000,
            "message": "ERROR AnalysisException: Path does not exist: s3://raw/orders/dt=2025-02-28/",
            "ingestionTime": 1709289613000
        }
    ]
}
```

---

### Get Log Events from Stream

**Purpose:** Read a specific log stream (e.g., one Glue job run).

**Command:**

```bash
aws logs get-log-events \
  --log-group-name /aws-glue/jobs/output \
  --log-stream-name jr_a1b2c3d4 \
  --limit 100 \
  --start-from-head
```

---

### Create Log Group

**Purpose:** Pre-create a log group with retention for custom applications.

**Command:**

```bash
aws logs create-log-group \
  --log-group-name /data-platform/pipeline-orchestrator \
  --tags Environment=prod,Team=data-platform

aws logs put-retention-policy \
  --log-group-name /data-platform/pipeline-orchestrator \
  --retention-in-days 30
```

---

### Put Log Events

**Purpose:** Ship custom application logs to CloudWatch.

**Command:**

```bash
aws logs put-log-events \
  --log-group-name /data-platform/pipeline-orchestrator \
  --log-stream-name orchestrator-$(date +%Y%m%d) \
  --log-events '[
    {"timestamp": 1709289612000, "message": "Started pipeline orders-ingest for dt=2025-03-01"},
    {"timestamp": 1709289613000, "message": "Glue job orders-daily-etl triggered run_id=jr_xyz789"}
  ]'
```

**Example Output:**

```json
{
    "nextSequenceToken": "49604745383306185959659359489151770395781265848471648903180826179106148562789156"
}
```

---

### Create Metric Filter

**Purpose:** Turn log patterns into CloudWatch metrics for alarming.

**Command:**

```bash
aws logs put-metric-filter \
  --log-group-name /aws/lambda/s3-landing-validator \
  --filter-name LambdaErrors \
  --filter-pattern "?ERROR ?Exception ?Traceback" \
  --metric-transformations '{
    "metricName": "PipelineErrors",
    "metricNamespace": "DataPlatform/Lambda",
    "metricValue": "1",
    "defaultValue": 0
  }'
```

---

### Export Logs to S3

**Purpose:** Archive logs for long-term retention or compliance.

**Command:**

```bash
aws logs create-export-task \
  --log-group-name /aws-glue/jobs/output \
  --from 1709251200000 \
  --to 1709337600000 \
  --destination etl-artifacts \
  --destination-prefix cloudwatch-exports/glue-logs/2025-03-01/
```

**Example Output:**

```json
{
    "taskId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

---

## Advanced Commands

### Insights Query (Start)

```bash
QUERY_ID=$(aws logs start-query \
  --log-group-name /aws/lambda/s3-landing-validator \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 20' \
  --query 'queryId' --output text)

aws logs get-query-results --query-id "$QUERY_ID"
```

### Subscription Filter to Lambda/Kinesis

```bash
aws logs put-subscription-filter \
  --log-group-name /aws/lambda/s3-landing-validator \
  --filter-name forward-to-security \
  --filter-pattern "" \
  --destination-arn arn:aws:lambda:us-east-1:123456789012:function:log-processor
```

### Encrypt Log Group with KMS

```bash
aws logs associate-kms-key \
  --log-group-name /data-platform/pipeline-orchestrator \
  --kms-key-id arn:aws:kms:us-east-1:123456789012:key/abcd1234-5678-90ab-cdef-1234567890ab
```

---

## Python Boto3 Examples

### Basic — Structured Logging to CloudWatch

```python
import json
import logging
from datetime import datetime, timezone

import boto3

logger = logging.getLogger(__name__)


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "pipeline": getattr(record, "pipeline", "unknown"),
        })


def setup_json_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.getLogger().handlers = [handler]
    logging.getLogger().setLevel(logging.INFO)
```

### Production-Ready — CloudWatch Logs Client

```python
import logging
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class CloudWatchLogWriter:
    def __init__(self, log_group: str, log_stream: str, region: str = "us-east-1"):
        self.client = boto3.client("logs", region_name=region)
        self.log_group = log_group
        self.log_stream = log_stream
        self.sequence_token: str | None = None
        self._ensure_stream()

    def _ensure_stream(self) -> None:
        try:
            self.client.create_log_group(logGroupName=self.log_group)
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ResourceAlreadyExistsException":
                raise
        try:
            self.client.create_log_stream(
                logGroupName=self.log_group,
                logStreamName=self.log_stream,
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ResourceAlreadyExistsException":
                raise

    def write(self, message: str) -> None:
        event = {"timestamp": int(time.time() * 1000), "message": message}
        kwargs: dict[str, Any] = {
            "logGroupName": self.log_group,
            "logStreamName": self.log_stream,
            "logEvents": [event],
        }
        if self.sequence_token:
            kwargs["sequenceToken"] = self.sequence_token

        try:
            resp = self.client.put_log_events(**kwargs)
            self.sequence_token = resp.get("nextSequenceToken")
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "InvalidSequenceTokenException":
                self.sequence_token = exc.response["Error"]["Message"].split()[-1]
                self.write(message)
            else:
                raise
```

### Run Logs Insights Query

```python
import boto3
import time


def find_glue_errors(hours: int = 6) -> list[str]:
    logs = boto3.client("logs")
    end = int(time.time())
    start = end - hours * 3600

    qid = logs.start_query(
        logGroupNames=["/aws-glue/jobs/output"],
        startTime=start,
        endTime=end,
        queryString="""
            fields @timestamp, @message
            | filter @message like /ERROR|Exception|AnalysisException/
            | sort @timestamp desc
            | limit 50
        """,
    )["queryId"]

    while True:
        result = logs.get_query_results(queryId=qid)
        if result["status"] in {"Complete", "Failed", "Cancelled"}:
            break
        time.sleep(1)

    return [row[1]["value"] for row in result.get("results", []) if len(row) > 1]
```

---

## Security Considerations

- Set **retention policies** on all log groups — unbounded retention increases cost and exposure.
- Encrypt sensitive log groups with **customer-managed KMS keys**.
- Restrict **`logs:FilterLogEvents`** and **`logs:GetLogEvents`** to authorized roles.
- Never log **PII, credentials, or full SQL** with sensitive literals — redact in application code.
- Audit **subscription filters** — they can exfiltrate logs to Lambda/Kinesis/Firehose destinations.

---

## Troubleshooting

| Error / Symptom | Root Cause | Resolution |
|-----------------|------------|------------|
| `ResourceNotFoundException` | Log group/stream missing | Create log group; Lambda creates on first invoke |
| `InvalidSequenceTokenException` | Concurrent writes to stream | Retry with returned sequence token |
| `DataAlreadyAcceptedException` | Duplicate timestamp events | Add millisecond offset to timestamps |
| Empty filter results | Wrong pattern syntax | Test pattern in Logs Insights console first |
| Glue logs missing | Continuous logging disabled | Set `--enable-continuous-cloudwatch-log` on job |
| Export task fails | S3 bucket policy missing | Grant `logs.amazonaws.com` write to destination bucket |

---

## Best Practices

- Use **structured JSON logging** in all pipeline code for searchable fields.
- Set retention: **14 days** for dev, **30–90 days** for prod, **export to S3** for compliance archives.
- Create **metric filters** for `ERROR`, `FAILED`, and `Timeout` patterns on critical log groups.
- Use **Logs Insights** for investigations; use **`aws logs tail`** for live debugging.
- Include **`request_id`**, **`pipeline`**, **`dt`**, and **`run_id`** in every log line.
- One **log stream per job run** for custom apps; avoid mixing unrelated runs in one stream.
- Monitor **StoredBytes** per log group; adjust retention or export old logs.
- Wire **subscription filters** to security SIEM only when required — they add cost and complexity.
