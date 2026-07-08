# DynamoDB — Python Boto3 Examples

## Service Overview

This guide provides production-oriented **Boto3** patterns for DynamoDB in data engineering workflows: batch ingestion, stream consumers, S3 exports, paginated reads, and error handling with structured logging.

**Prerequisites:**
- Python 3.9+
- `boto3`, `botocore`
- IAM permissions for target tables, streams, and S3 export buckets

---

## AWS CLI Commands

Quick reference for operations commonly paired with Python scripts:

```bash
# Verify table exists
aws dynamodb describe-table --table-name pipeline-metadata --query 'Table.TableStatus'

# Export for offline analytics
aws dynamodb export-table-to-point-in-time \
  --table-arn arn:aws:dynamodb:us-east-1:123456789012:table/user-events-prod \
  --s3-bucket my-data-lake-raw \
  --s3-prefix exports/user-events/

# Check export status
aws dynamodb describe-export --export-arn arn:aws:dynamodb:us-east-1:123456789012:export/01234567890123456789012
```

---

## Advanced Commands

### Wait for Table Active

```bash
aws dynamodb wait table-exists --table-name pipeline-metadata
```

### Trigger On-Demand Backup Before Migration

```bash
aws dynamodb create-backup \
  --table-name user-events-prod \
  --backup-name user-events-pre-migration-20250301
```

---

## Python (Boto3) Examples

### Basic — Resource API Table Operations

```python
import boto3

dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
table = dynamodb.Table("pipeline-metadata")

# Put checkpoint
table.put_item(
    Item={
        "job_id": "orders-daily-etl",
        "run_date": "2025-03-01",
        "status": "RUNNING",
        "checkpoint_offset": 0,
    }
)

# Conditional update — prevent overwriting SUCCESS
table.update_item(
    Key={"job_id": "orders-daily-etl", "run_date": "2025-03-01"},
    UpdateExpression="SET #s = :running, updated_at = :ts",
    ConditionExpression="attribute_not_exists(#s) OR #s <> :success",
    ExpressionAttributeNames={"#s": "status"},
    ExpressionAttributeValues={
        ":running": "RUNNING",
        ":success": "SUCCESS",
        ":ts": "2025-03-01T06:00:00Z",
    },
)
```

### Paginated Query with Boto3 Paginator

```python
import boto3

client = boto3.client("dynamodb")
paginator = client.get_paginator("query")

pages = paginator.paginate(
    TableName="pipeline-metadata",
    KeyConditionExpression="job_id = :jid",
    ExpressionAttributeValues={":jid": {"S": "orders-daily-etl"}},
)

for page in pages:
    for item in page["Items"]:
        print(item["run_date"]["S"], item.get("status", {}).get("S"))
```

### Production-Ready — Batch Ingest with Exponential Backoff

```python
import logging
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def batch_write_with_retry(
    table_name: str,
    items: list[dict[str, Any]],
    max_retries: int = 5,
) -> None:
    """Write items in batches of 25 with unprocessed item retry."""
    client = boto3.client("dynamodb")
    request_items = {
        table_name: [{"PutRequest": {"Item": _to_dynamo(item)}} for item in items]
    }

    for attempt in range(max_retries):
        response = client.batch_write_item(RequestItems=request_items)
        unprocessed = response.get("UnprocessedItems", {})
        if not unprocessed:
            logger.info("Successfully wrote %d items", len(items))
            return
        request_items = unprocessed
        sleep = 2**attempt * 0.1
        logger.warning("Retrying %d unprocessed items (attempt %d)", len(unprocessed[table_name]), attempt + 1)
        time.sleep(sleep)

    raise RuntimeError(f"Failed to write all items after {max_retries} retries")


def _to_dynamo(item: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Minimal serializer for string/number attributes."""
    result = {}
    for key, value in item.items():
        if isinstance(value, (int, float)):
            result[key] = {"N": str(value)}
        else:
            result[key] = {"S": str(value)}
    return result
```

### Stream Consumer — CDC to Downstream Pipeline

```python
import json
import logging

import boto3

logger = logging.getLogger(__name__)


def process_stream_batch(records: list[dict]) -> None:
    """Transform DynamoDB stream records for S3/Kinesis sink."""
    for record in records:
        if record["eventName"] not in ("INSERT", "MODIFY"):
            continue
        new_image = record["dynamodb"].get("NewImage", {})
        payload = {k: list(v.values())[0] for k, v in new_image.items()}
        logger.info("CDC event: %s", json.dumps(payload))


def poll_stream_once(stream_arn: str, shard_id: str, iterator: str | None = None) -> str:
    streams = boto3.client("dynamodbstreams")
    if iterator is None:
        resp = streams.get_shard_iterator(
            StreamArn=stream_arn,
            ShardId=shard_id,
            ShardIteratorType="LATEST",
        )
        iterator = resp["ShardIterator"]

    records_resp = streams.get_records(ShardIterator=iterator, Limit=100)
    process_stream_batch(records_resp["Records"])
    return records_resp["NextShardIterator"]
```

### Export Table to S3 (Analytics Pipeline)

```python
import logging
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def export_table_to_s3(
    table_arn: str,
    bucket: str,
    prefix: str,
    export_format: str = "DYNAMODB_JSON",
) -> str:
    client = boto3.client("dynamodb")
    export_time = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    s3_prefix = f"{prefix.rstrip('/')}/{export_time}/"

    try:
        resp = client.export_table_to_point_in_time(
            TableArn=table_arn,
            S3Bucket=bucket,
            S3Prefix=s3_prefix,
            ExportFormat=export_format,
        )
        export_arn = resp["ExportDescription"]["ExportArn"]
        logger.info("Started export %s → s3://%s/%s", export_arn, bucket, s3_prefix)
        return export_arn
    except ClientError as exc:
        logger.error("Export failed: %s", exc.response["Error"]["Message"])
        raise
```

### Atomic Counter for Pipeline Metrics

```python
import boto3

table = boto3.resource("dynamodb").Table("pipeline-metrics")

table.update_item(
    Key={"metric_name": "rows_ingested", "date": "2025-03-01"},
    UpdateExpression="ADD #cnt :inc SET #updated = :ts",
    ExpressionAttributeNames={"#cnt": "count", "#updated": "updated_at"},
    ExpressionAttributeValues={
        ":inc": 1000,
        ":ts": "2025-03-01T06:30:00Z",
    },
    ReturnValues="UPDATED_NEW",
)
```

### Type Serializer with `boto3.dynamodb.types.TypeSerializer`

```python
from boto3.dynamodb.types import TypeSerializer

serializer = TypeSerializer()

item = {
    "job_id": "orders-daily-etl",
    "run_date": "2025-03-01",
    "tags": ["prod", "critical"],
    "metadata": {"source": "kinesis", "version": 2},
    "rows_processed": 1250000,
}

dynamo_item = {k: serializer.serialize(v) for k, v in item.items()}
```

### Error Handling Pattern

```python
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def safe_get_item(table_name: str, key: dict) -> dict | None:
    table = boto3.resource("dynamodb").Table(table_name)
    try:
        resp = table.get_item(Key=key, ConsistentRead=True)
        return resp.get("Item")
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "ResourceNotFoundException":
            logger.error("Table %s not found", table_name)
        elif code == "ProvisionedThroughputExceededException":
            logger.warning("Throttled — retry with backoff")
        raise
```

---

## Security Considerations

- Never hardcode AWS credentials; use **IAM roles** (Glue job role, Lambda execution role, EC2 instance profile).
- Use **`ConditionExpression`** to prevent race conditions on pipeline state updates.
- Encrypt exports with **SSE-KMS** on the destination S3 bucket.
- Limit stream Lambda permissions to `dynamodb:GetRecords`, `dynamodb:DescribeStream` on specific stream ARNs.
- Sanitize log output — stream payloads may contain PII.

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `TypeError: Float types are not supported` | Float in item | Use `Decimal` from `decimal` module |
| Batch writer silently drops items | Unhandled unprocessed keys | Implement retry loop on `UnprocessedItems` |
| `ConditionalCheckFailedException` | Concurrent writers | Use idempotent keys or retry logic |
| Empty paginator results | Wrong key condition | Validate partition/sort key types |
| Export stuck in IN_PROGRESS | Large table | Wait; check `describe_export`; verify S3 bucket policy |

---

## Best Practices

- Use **`boto3.resource`** for high-level CRUD; use **`boto3.client`** for exports, backups, and paginators.
- Always use **`batch_writer`** context manager for bulk loads (handles 25-item chunking).
- Convert floats to **`Decimal`** before writes.
- Implement **idempotent consumers** for DynamoDB Streams (at-least-once delivery).
- Use **`ReturnValues`** on updates when downstream steps need the new state.
- Set **`max_pool_connections`** on the botocore config for high-throughput writers.
- Pair exports with **Glue crawlers** to catalog DynamoDB JSON in the data lake.
- Monitor **`UserErrors`** and **`SystemErrors`** CloudWatch metrics from application logs.
