# SQS — Queues and Messaging

## Service Overview

**Amazon Simple Queue Service (SQS)** is a fully managed message queuing service for decoupling and scaling microservices, distributed systems, and serverless pipelines. Data engineers use SQS to buffer ingestion events, distribute ETL work items across workers, absorb traffic spikes, and build reliable at-least-once processing pipelines.

**Common use cases:**
- Queue S3 landing events for parallel file processors (Lambda/ECS workers)
- Distribute partition-level Spark/ETL tasks across a worker fleet
- Buffer CDC or API poll records before Glue/Lambda transformation
- Dead-letter failed messages for inspection and replay

**When to use it:** Work queues with competing consumers, backpressure between pipeline stages, or async handoff where SNS fan-out is not required.

**Queue types:**
- **Standard** — best-effort ordering, at-least-once delivery, high throughput
- **FIFO** — strict ordering, exactly-once processing (with deduplication), lower TPS

**Required IAM permissions (examples):** `sqs:CreateQueue`, `sqs:SendMessage`, `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:GetQueueAttributes`, `sqs:SetQueueAttributes`

---

## AWS CLI Commands

### Create Standard Queue

**Purpose:** Create a work queue for ETL file processing jobs.

**Command:**

```bash
aws sqs create-queue \
  --queue-name etl-work-queue \
  --attributes '{
    "VisibilityTimeout": "300",
    "MessageRetentionPeriod": "1209600",
    "ReceiveMessageWaitTimeSeconds": "20",
    "KmsMasterKeyId": "alias/data-platform-sqs"
  }' \
  --tags Team=DataEng,Pipeline=ingestion
```

**Example Output:**

```json
{
    "QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/etl-work-queue"
}
```

---

### Create FIFO Queue with DLQ

**Purpose:** Ordered processing with dead-letter capture for failed records.

**Command:**

```bash
# Dead-letter queue first
aws sqs create-queue \
  --queue-name etl-failed-records-dlq.fifo \
  --attributes FifoQueue=true,ContentBasedDeduplication=true

DLQ_ARN=$(aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/etl-failed-records-dlq.fifo \
  --attribute-names QueueArn \
  --query 'Attributes.QueueArn' --output text)

aws sqs create-queue \
  --queue-name orders-ingest.fifo \
  --attributes "{
    \"FifoQueue\": \"true\",
    \"ContentBasedDeduplication\": \"true\",
    \"VisibilityTimeout\": \"120\",
    \"RedrivePolicy\": \"{\\\"deadLetterTargetArn\\\":\\\"${DLQ_ARN}\\\",\\\"maxReceiveCount\\\":\\\"3\\\"}\"
  }"
```

---

### Send Message

**Purpose:** Enqueue a file processing job after S3 upload.

**Command:**

```bash
aws sqs send-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/etl-work-queue \
  --message-body '{
    "bucket": "raw-data-bucket",
    "key": "events/year=2025/month=03/day=01/part-00000.parquet",
    "job_type": "parquet_validate",
    "run_id": "run-20250301-001"
  }' \
  --message-attributes '{
    "job_type": {"DataType": "String", "StringValue": "parquet_validate"}
  }'
```

**Example Output:**

```json
{
    "MessageId": "abc12345-6789-0def-ghij-klmnopqrstuv",
    "MD5OfMessageBody": "a1b2c3d4e5f6..."
}
```

---

### Receive and Delete Message (Worker Pattern)

**Purpose:** Poll, process, and acknowledge a job.

**Command:**

```bash
QUEUE_URL="https://sqs.us-east-1.amazonaws.com/123456789012/etl-work-queue"

MSG=$(aws sqs receive-message \
  --queue-url "$QUEUE_URL" \
  --max-number-of-messages 1 \
  --wait-time-seconds 20 \
  --visibility-timeout 300 \
  --query 'Messages[0]' \
  --output json)

echo "$MSG" | jq .

RECEIPT=$(echo "$MSG" | jq -r '.ReceiptHandle')
aws sqs delete-message --queue-url "$QUEUE_URL" --receipt-handle "$RECEIPT"
```

---

### Get Queue Depth

**Purpose:** Monitor backlog for autoscaling ECS/Lambda consumers.

**Command:**

```bash
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/etl-work-queue \
  --attribute-names ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible,ApproximateNumberOfMessagesDelayed \
  --output table
```

**Example Output:**

```
ApproximateNumberOfMessages:           1523
ApproximateNumberOfMessagesNotVisible: 48
ApproximateNumberOfMessagesDelayed:    0
```

---

### Purge Queue (Non-Production)

**Purpose:** Clear all messages during testing — irreversible.

**Command:**

```bash
aws sqs purge-queue \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/etl-work-queue-dev
```

---

## Advanced Commands

### Long Polling Batch Receive

**Purpose:** Efficiently drain queue with fewer API calls.

**Command:**

```bash
aws sqs receive-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/etl-work-queue \
  --max-number-of-messages 10 \
  --wait-time-seconds 20 \
  --attribute-names All \
  --message-attribute-names All
```

---

### Change Visibility Timeout (Extend Processing)

**Purpose:** Prevent redelivery while a long Spark sub-job runs.

**Command:**

```bash
aws sqs change-message-visibility \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/etl-work-queue \
  --receipt-handle "<receipt-handle>" \
  --visibility-timeout 900
```

---

### Send Message Batch

**Purpose:** Enqueue hundreds of partition jobs efficiently.

**Command:**

```bash
aws sqs send-message-batch \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/etl-work-queue \
  --entries '[
    {"Id":"1","MessageBody":"{\"partition\":\"dt=2025-03-01/h=00\"}"},
    {"Id":"2","MessageBody":"{\"partition\":\"dt=2025-03-01/h=01\"}"},
    {"Id":"3","MessageBody":"{\"partition\":\"dt=2025-03-01/h=02\"}"}
  ]'
```

---

### Queue Policy for SNS / S3 Events

**Purpose:** Allow SNS topic to deliver messages to SQS.

**Command:**

```bash
aws sqs set-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/downstream-etl-queue \
  --attributes '{
    "Policy": "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Principal\":{\"Service\":\"sns.amazonaws.com\"},\"Action\":\"sqs:SendMessage\",\"Resource\":\"arn:aws:sqs:us-east-1:123456789012:downstream-etl-queue\",\"Condition\":{\"ArnEquals\":{\"aws:SourceArn\":\"arn:aws:sns:us-east-1:123456789012:dataset-ready-events\"}}}]}"
  }'
```

---

## Python (Boto3) Examples

### Send Job Message

```python
import json
import boto3

sqs = boto3.client("sqs")

def enqueue_etl_job(queue_url: str, job: dict) -> str:
    resp = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(job),
    )
    return resp["MessageId"]
```

---

## Security Considerations

- Encrypt queues with **SSE-SQS** or **SSE-KMS**; use KMS for audit and cross-account control.
- Scope IAM policies to specific **queue ARNs**; separate producer and consumer roles.
- Never expose queue URLs publicly; use **VPC endpoints** for private subnet access.
- Sanitize message bodies — avoid credentials or raw PII in queue payloads.
- Protect **DLQ** access; failed messages may contain sensitive data.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| Messages reprocessed repeatedly | Visibility timeout too short | Increase timeout or extend during processing |
| `AccessDenied` on receive | Consumer lacks permissions | Grant `sqs:ReceiveMessage`, `sqs:DeleteMessage` |
| FIFO `InvalidParameter` | Missing MessageGroupId | Add group ID on send |
| Growing DLQ | Poison messages or code bug | Inspect DLQ; fix handler; replay after fix |
| `AWS.SimpleQueueService.NonExistentQueue` | Wrong URL or region | Verify queue URL from `get-queue-url` |

---

## Best Practices

- Set **visibility timeout** ≥ max processing time (include cold start).
- Use **long polling** (`WaitTimeSeconds=20`) to reduce empty receives and cost.
- Configure **DLQ** with `maxReceiveCount=3–5` for all production queues.
- Design consumers for **idempotency** (at-least-once delivery).
- Scale workers on **ApproximateNumberOfMessagesVisible** via CloudWatch alarms or ECS autoscaling.
- Use **FIFO queues** only when strict ordering is required — they limit throughput.
- Batch send/receive (up to 10 messages) to reduce API costs at high volume.
