# EventBridge — Python Boto3 Examples

## Service Overview

The Boto3 `events` client provides programmatic access to EventBridge rules, targets, archives, and custom event publishing — essential for automating data pipeline triggers and observability hooks.

---

## Basic Examples

### Session and Client

```python
import boto3

session = boto3.Session(profile_name="data-engineer", region_name="us-east-1")
events = session.client("events")
```

### Put Custom Event

```python
response = events.put_events(
    Entries=[
        {
            "Source": "com.mycompany.etl",
            "DetailType": "PipelineCompleted",
            "Detail": '{"pipeline": "orders-daily", "status": "SUCCESS", "rows": 1500000}',
            "EventBusName": "data-pipeline-bus",
        }
    ]
)
if response["FailedEntryCount"] > 0:
    raise RuntimeError(f"Failed entries: {response['Entries']}")
```

### Create Scheduled Rule

```python
events.put_rule(
    Name="nightly-glue-crawler",
    ScheduleExpression="cron(0 2 * * ? *)",
    State="ENABLED",
    Description="Start Glue crawler at 02:00 UTC daily",
)

events.put_targets(
    Rule="nightly-glue-crawler",
    Targets=[
        {
            "Id": "glue-crawler-target",
            "Arn": "arn:aws:glue:us-east-1:123456789012:crawler/orders-crawler",
            "RoleArn": "arn:aws:iam::123456789012:role/EventBridgeGlueRole",
        }
    ],
)
```

---

## Production-Ready Examples

### S3 Landing Zone Trigger Rule

```python
import json
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

RULE_NAME = "s3-raw-landing-trigger"
BUCKET = "my-data-lake-raw"
PREFIX = "orders/"
LAMBDA_ARN = "arn:aws:lambda:us-east-1:123456789012:function:process-raw-orders"


def create_s3_trigger_rule(events_client) -> None:
    event_pattern = {
        "source": ["aws.s3"],
        "detail-type": ["Object Created"],
        "detail": {
            "bucket": {"name": [BUCKET]},
            "object": {"key": [{"prefix": PREFIX}]},
        },
    }

    events_client.put_rule(
        Name=RULE_NAME,
        EventPattern=json.dumps(event_pattern),
        State="ENABLED",
        Description=f"Trigger ETL for s3://{BUCKET}/{PREFIX}",
    )

    events_client.put_targets(
        Rule=RULE_NAME,
        Targets=[
            {
                "Id": "lambda-etl",
                "Arn": LAMBDA_ARN,
                "InputTransformer": {
                    "InputPathsMap": {
                        "bucket": "$.detail.bucket.name",
                        "key": "$.detail.object.key",
                    },
                    "InputTemplate": '{"s3_uri": "s3://<bucket>/<key>"}',
                },
            }
        ],
    )
    logger.info("Created rule %s", RULE_NAME)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_s3_trigger_rule(boto3.client("events"))
```

### Batch Publish with Error Handling

```python
import json
import logging
from typing import Iterable

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
MAX_BATCH = 10  # EventBridge limit per PutEvents call


def publish_pipeline_events(
    events_client,
    bus_name: str,
    records: Iterable[dict],
) -> int:
    """Publish pipeline status events; returns count of successful entries."""
    entries = [
        {
            "Source": "com.mycompany.etl",
            "DetailType": "PipelineStatus",
            "Detail": json.dumps(record),
            "EventBusName": bus_name,
        }
        for record in records
    ]

    success = 0
    for i in range(0, len(entries), MAX_BATCH):
        batch = entries[i : i + MAX_BATCH]
        try:
            resp = events_client.put_events(Entries=batch)
        except ClientError:
            logger.exception("PutEvents failed for batch starting at %d", i)
            raise

        failed = resp["FailedEntryCount"]
        if failed:
            for entry in resp["Entries"]:
                if "ErrorCode" in entry:
                    logger.error(
                        "Entry failed: %s — %s",
                        entry["ErrorCode"],
                        entry.get("ErrorMessage"),
                    )
        success += len(batch) - failed

    return success
```

### List Rules with Pagination

```python
def list_enabled_rules(events_client, bus_name: str = "default") -> list[str]:
    paginator = events_client.get_paginator("list_rules")
    names = []
    for page in paginator.paginate(EventBusName=bus_name):
        for rule in page["Rules"]:
            if rule.get("State") == "ENABLED":
                names.append(rule["Name"])
    return names
```

---

## Error Handling

```python
from botocore.exceptions import ClientError, BotoCoreError

events = boto3.client("events")

try:
    events.put_events(
        Entries=[{
            "Source": "com.mycompany.etl",
            "DetailType": "Test",
            "Detail": "{}",
        }]
    )
except ClientError as exc:
    code = exc.response["Error"]["Code"]
    if code == "ResourceNotFoundException":
        print("Event bus not found")
    elif code == "LimitExceededException":
        print("Rate or quota limit exceeded")
    else:
        raise
except BotoCoreError:
    logger.exception("Network or credential error")
    raise
```

---

## Security Considerations

- Never embed secrets in event `Detail` — use Secrets Manager ARNs or opaque reference IDs.
- Validate event payloads in consumers; treat EventBridge as an untrusted input boundary for cross-account buses.
- Use IAM condition keys `events:source`, `events:detail-type` when allowing `PutEvents`.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `FailedEntryCount > 0` | Log `Entries[].ErrorCode`; common cause is malformed JSON in `Detail` |
| Lambda not triggered | Add permission: `lambda:InvokeFunction` for `events.amazonaws.com` |
| Duplicate processing | Implement idempotency keys in `Detail`; EventBridge delivers at-least-once |

---

## Best Practices

- Wrap `put_events` in retry logic with exponential backoff for throttling.
- Use `json.dumps()` for `Detail` — must be a JSON string, not a dict.
- Batch up to 10 entries per `put_events` call for throughput.
- Emit structured events with `pipeline`, `run_id`, `status`, and `timestamp` fields for observability.
