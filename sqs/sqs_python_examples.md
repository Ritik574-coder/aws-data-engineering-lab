# SQS — Python Boto3 Examples

## Service Overview

Boto3 SQS client for building reliable queue producers, long-polling consumers, DLQ replay utilities, and pipeline backpressure patterns in data engineering systems.

---

## AWS CLI Commands

### Quick Reference — Queue Depth

```bash
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/etl-work-queue \
  --attribute-names ApproximateNumberOfMessages
```

---

## Advanced Commands

### Redrive DLQ Messages to Source Queue

```bash
# Use AWS Console "Start DLQ redrive" or API via SQS redrive-allow-policy (SQS DLQ redrive feature)
aws sqs start-message-move-task \
  --source-arn arn:aws:sqs:us-east-1:123456789012:etl-failed-records-dlq.fifo \
  --destination-arn arn:aws:sqs:us-east-1:123456789012:orders-ingest.fifo
```

---

## Python (Boto3) Examples

### Production-Ready — Long-Polling Consumer

```python
import json
import logging
import signal
import time
from typing import Callable

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

_running = True


def _handle_shutdown(signum, frame):
    global _running
    _running = False


signal.signal(signal.SIGTERM, _handle_shutdown)
signal.signal(signal.SIGINT, _handle_shutdown)


def consume_queue(
    queue_url: str,
    handler: Callable[[dict], None],
    max_messages: int = 10,
    wait_seconds: int = 20,
    visibility_timeout: int = 300,
) -> None:
    sqs = boto3.client("sqs")

    while _running:
        try:
            resp = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_seconds,
                VisibilityTimeout=visibility_timeout,
                MessageAttributeNames=["All"],
            )
        except ClientError:
            logger.exception("Failed to receive messages")
            time.sleep(5)
            continue

        messages = resp.get("Messages", [])
        if not messages:
            continue

        for msg in messages:
            receipt = msg["ReceiptHandle"]
            try:
                body = json.loads(msg["Body"])
                handler(body)
                sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt)
                logger.info("Processed message %s", msg["MessageId"])
            except Exception:
                logger.exception("Handler failed for message %s", msg["MessageId"])
                # Message returns to queue after visibility timeout
```

---

### Send Batch with Partial Failure Handling

```python
import json
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def send_job_batch(queue_url: str, jobs: list[dict]) -> tuple[int, int]:
    sqs = boto3.client("sqs")
    sent, failed = 0, 0

    for i in range(0, len(jobs), 10):
        batch = jobs[i : i + 10]
        entries = [
            {"Id": str(idx), "MessageBody": json.dumps(job)}
            for idx, job in enumerate(batch)
        ]
        try:
            resp = sqs.send_message_batch(QueueUrl=queue_url, Entries=entries)
            sent += len(resp.get("Successful", []))
            failed += len(resp.get("Failed", []))
            for fail in resp.get("Failed", []):
                logger.error("Batch send failed: %s", fail)
        except ClientError:
            logger.exception("send_message_batch error")
            failed += len(batch)

    return sent, failed
```

---

### Extend Visibility During Long Processing

```python
import boto3


def extend_visibility(queue_url: str, receipt_handle: str, timeout_sec: int = 900) -> None:
    sqs = boto3.client("sqs")
    sqs.change_message_visibility(
        QueueUrl=queue_url,
        ReceiptHandle=receipt_handle,
        VisibilityTimeout=timeout_sec,
    )
```

---

### Create Queue with DLQ (Idempotent)

```python
import json

import boto3


def ensure_queue_with_dlq(
    queue_name: str,
    dlq_name: str,
    visibility_timeout: int = 300,
    max_receive_count: int = 3,
) -> tuple[str, str]:
    sqs = boto3.client("sqs")

    dlq_resp = sqs.create_queue(
        QueueName=dlq_name,
        Attributes={"MessageRetentionPeriod": "1209600"},
    )
    dlq_url = dlq_resp["QueueUrl"]
    dlq_arn = sqs.get_queue_attributes(
        QueueUrl=dlq_url, AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]

    redrive = json.dumps({"deadLetterTargetArn": dlq_arn, "maxReceiveCount": str(max_receive_count)})
    q_resp = sqs.create_queue(
        QueueName=queue_name,
        Attributes={
            "VisibilityTimeout": str(visibility_timeout),
            "ReceiveMessageWaitTimeSeconds": "20",
            "RedrivePolicy": redrive,
        },
    )
    return q_resp["QueueUrl"], dlq_url
```

---

### Monitor Queue Backlog

```python
import boto3


def get_backlog_metrics(queue_url: str) -> dict:
    sqs = boto3.client("sqs")
    attrs = sqs.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=[
            "ApproximateNumberOfMessages",
            "ApproximateNumberOfMessagesNotVisible",
            "ApproximateNumberOfMessagesDelayed",
        ],
    )["Attributes"]
    return {k: int(v) for k, v in attrs.items()}
```

---

### Replay Messages from DLQ

```python
import json

import boto3


def replay_dlq(dlq_url: str, target_queue_url: str, max_messages: int = 100) -> int:
    sqs = boto3.client("sqs")
    replayed = 0

    while replayed < max_messages:
        resp = sqs.receive_message(
            QueueUrl=dlq_url,
            MaxNumberOfMessages=min(10, max_messages - replayed),
            WaitTimeSeconds=5,
        )
        messages = resp.get("Messages", [])
        if not messages:
            break

        for msg in messages:
            sqs.send_message(QueueUrl=target_queue_url, MessageBody=msg["Body"])
            sqs.delete_message(QueueUrl=dlq_url, ReceiptHandle=msg["ReceiptHandle"])
            replayed += 1

    return replayed
```

---

### FIFO Producer with Deduplication

```python
import hashlib
import json

import boto3


def send_fifo_message(queue_url: str, group_id: str, payload: dict) -> str:
    sqs = boto3.client("sqs")
    body = json.dumps(payload)
    dedup_id = hashlib.sha256(body.encode()).hexdigest()

    resp = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=body,
        MessageGroupId=group_id,
        MessageDeduplicationId=dedup_id,
    )
    return resp["MessageId"]
```

---

## Security Considerations

- Use **separate IAM roles** for producers (send only) and consumers (receive/delete only).
- Enable **server-side encryption** on all queues handling production data.
- Validate and schema-check message bodies before processing to prevent injection.
- Restrict DLQ replay to **break-glass roles** with CloudTrail alerting.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `ReceiptHandleIsInvalid` | Message already deleted or expired | Do not reuse receipt handles |
| Duplicate processing | At-least-once semantics | Implement idempotent handlers with dedup keys |
| Batch partial failure | One entry invalid | Retry failed entries from `Failed` list |
| Consumer starvation | One slow message blocking batch | Process messages individually; use partial batch failure (Lambda) |
| High `NotVisible` count | Workers crashing mid-process | Fix handler; tune visibility timeout |

---

## Best Practices

- Store large payloads in **S3**; pass bucket/key references in SQS messages.
- Emit **processing metrics** (lag, age of oldest message) to CloudWatch dashboards.
- Use **heartbeat** visibility extensions for jobs longer than 5 minutes.
- Tag queues with `Pipeline`, `Stage`, and `Environment` for operations clarity.
- Test **poison pill** handling by deliberately sending malformed messages to staging DLQ.
