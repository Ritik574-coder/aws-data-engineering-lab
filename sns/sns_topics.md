# SNS — Topics and Subscriptions

## Service Overview

**Amazon Simple Notification Service (SNS)** is a fully managed pub/sub messaging service. Data engineering teams use SNS to broadcast pipeline events, alert on job failures, notify downstream systems when datasets land in S3, and integrate with Lambda, SQS, email, and PagerDuty for operational visibility.

**Common use cases:**
- Publish alerts when Glue/EMR/Step Functions jobs fail or succeed
- Notify analytics teams when curated tables are refreshed
- Fan-out S3 event notifications to multiple consumers via SNS → SQS
- Trigger Lambda functions for lightweight event routing and enrichment

**When to use it:** One-to-many messaging where multiple subscribers need the same event — job status broadcasts, operational alerts, and decoupled pipeline notifications.

**Required IAM permissions (examples):** `sns:CreateTopic`, `sns:Subscribe`, `sns:Publish`, `sns:ListSubscriptionsByTopic`, `sns:SetTopicAttributes`

---

## AWS CLI Commands

### Create Topic

**Purpose:** Create a topic for pipeline status notifications.

**Command:**

```bash
aws sns create-topic \
  --name data-pipeline-alerts \
  --attributes '{
    "DisplayName": "Data Pipeline Alerts",
    "KmsMasterKeyId": "alias/data-platform-sns"
  }' \
  --tags Team=DataEng,Environment=prod
```

**Example Output:**

```json
{
    "TopicArn": "arn:aws:sns:us-east-1:123456789012:data-pipeline-alerts"
}
```

---

### Subscribe Email Endpoint

**Purpose:** Send human-readable alerts to on-call engineers.

**Command:**

```bash
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789012:data-pipeline-alerts \
  --protocol email \
  --notification-endpoint data-oncall@example.com
```

**Note:** Recipient must confirm subscription via email link before messages are delivered.

---

### Subscribe SQS Queue (Fan-Out)

**Purpose:** Deliver the same pipeline event to a queue for async processing.

**Command:**

```bash
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789012:dataset-ready-events \
  --protocol sqs \
  --notification-endpoint arn:aws:sqs:us-east-1:123456789012:downstream-etl-queue \
  --attributes RawMessageDelivery=true
```

Ensure the SQS queue policy allows SNS to send messages.

---

### Publish Message

**Purpose:** Notify subscribers that a batch job completed.

**Command:**

```bash
aws sns publish \
  --topic-arn arn:aws:sns:us-east-1:123456789012:data-pipeline-alerts \
  --subject "EMR Job SUCCESS: orders-etl" \
  --message '{
    "pipeline": "orders-etl",
    "status": "SUCCESS",
    "run_date": "2025-03-01",
    "output_path": "s3://curated/orders/dt=2025-03-01/",
    "duration_sec": 1842
  }' \
  --message-attributes '{
    "severity": {"DataType": "String", "StringValue": "info"},
    "pipeline": {"DataType": "String", "StringValue": "orders-etl"}
  }'
```

**Example Output:**

```json
{
    "MessageId": "abc12345-6789-0def-ghij-klmnopqrstuv"
}
```

---

### List Subscriptions

**Purpose:** Audit who receives pipeline notifications.

**Command:**

```bash
aws sns list-subscriptions-by-topic \
  --topic-arn arn:aws:sns:us-east-1:123456789012:data-pipeline-alerts \
  --query 'Subscriptions[].{Protocol:Protocol,Endpoint:Endpoint,Status:SubscriptionArn}' \
  --output table
```

---

### Set Topic Policy (Allow S3 to Publish)

**Purpose:** Enable S3 event notifications to an SNS topic.

**Command:**

```bash
aws sns set-topic-attributes \
  --topic-arn arn:aws:sns:us-east-1:123456789012:s3-landing-events \
  --attribute-name Policy \
  --attribute-value '{
    "Version": "2012-10-17",
    "Statement": [{
      "Sid": "AllowS3Publish",
      "Effect": "Allow",
      "Principal": {"Service": "s3.amazonaws.com"},
      "Action": "SNS:Publish",
      "Resource": "arn:aws:sns:us-east-1:123456789012:s3-landing-events",
      "Condition": {
        "ArnLike": {"aws:SourceArn": "arn:aws:s3:::raw-data-bucket"},
        "StringEquals": {"aws:SourceAccount": "123456789012"}
      }
    }]
  }'
```

---

## Advanced Commands

### Filter Policy on SQS Subscription

**Purpose:** Route only failed job events to an alerting queue.

**Command:**

```bash
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789012:pipeline-events \
  --protocol sqs \
  --notification-endpoint arn:aws:sqs:us-east-1:123456789012:failure-alerts-queue \
  --attributes '{
    "FilterPolicy": "{\"status\":[\"FAILED\",\"TIMEOUT\"]}",
    "RawMessageDelivery": "true"
  }'
```

Publish messages with `MessageAttributes` matching filter keys.

---

### FIFO Topic for Ordered Pipeline Stages

**Purpose:** Guarantee ordered notifications for sequential pipeline stages.

**Command:**

```bash
aws sns create-topic \
  --name pipeline-stage-events.fifo \
  --attributes FifoTopic=true,ContentBasedDeduplication=true

aws sns publish \
  --topic-arn arn:aws:sns:us-east-1:123456789012:pipeline-stage-events.fifo \
  --message '{"stage":"curate","status":"complete"}' \
  --message-group-id orders-etl \
  --message-deduplication-id orders-etl-curate-20250301
```

---

### Message Archiving (Firehose / S3)

**Purpose:** Archive all pipeline notifications for audit and replay.

Configure SNS to deliver to Kinesis Firehose → S3 via subscription or use EventBridge Pipes for advanced routing.

---

## Python (Boto3) Examples

### Publish Pipeline Status

```python
import json
import boto3

sns = boto3.client("sns")

def publish_job_status(topic_arn: str, pipeline: str, status: str, details: dict) -> str:
    message = {"pipeline": pipeline, "status": status, **details}
    resp = sns.publish(
        TopicArn=topic_arn,
        Subject=f"{pipeline} — {status}",
        Message=json.dumps(message),
        MessageAttributes={
            "pipeline": {"DataType": "String", "StringValue": pipeline},
            "status": {"DataType": "String", "StringValue": status},
        },
    )
    return resp["MessageId"]
```

---

## Security Considerations

- Encrypt topics with **SSE-KMS**; restrict KMS key usage to SNS and authorized publishers.
- Use **topic policies** with `aws:SourceAccount` and `aws:SourceArn` conditions.
- Avoid PII in message bodies; reference S3 paths or job IDs instead.
- Restrict `sns:Publish` to specific IAM roles (Glue, Step Functions, Lambda).
- Confirm and audit **email/SMS subscriptions** regularly; remove stale endpoints.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `NotFound` on publish | Wrong region or deleted topic | Verify topic ARN and region |
| SQS not receiving messages | Queue policy blocks SNS | Add `aws:SourceArn` condition allowing SNS topic |
| Email not received | Subscription pending | Confirm subscription via email link |
| `InvalidParameter` FIFO | Missing MessageGroupId | Provide group and deduplication IDs |
| Filter policy no delivery | Attribute mismatch | Ensure publish uses matching MessageAttributes |

---

## Best Practices

- Standardize **message schema** (JSON) with `pipeline`, `status`, `run_id`, `timestamp`.
- Use **separate topics** for alerts (high priority) vs. informational events.
- Apply **filter policies** to reduce noise and downstream processing cost.
- Integrate with **EventBridge** for complex routing rules beyond SNS filters.
- Monitor **NumberOfMessagesPublished** and **NumberOfNotificationsFailed** in CloudWatch.
- Use **dead-letter queues** on SQS subscriptions for failed deliveries.
