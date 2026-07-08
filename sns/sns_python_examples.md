# SNS — Python Boto3 Examples

## Service Overview

Boto3 SNS client for publishing pipeline events, managing subscriptions, and integrating alerting into data engineering orchestration code.

---

## AWS CLI Commands

### Quick Reference — Publish Alert

```bash
aws sns publish \
  --topic-arn arn:aws:sns:us-east-1:123456789012:data-pipeline-alerts \
  --message '{"pipeline":"orders-etl","status":"FAILED","error":"OOM"}'
```

---

## Advanced Commands

### List All Topics with Tag Filter

```bash
aws sns list-topics --query 'Topics[?contains(TopicArn, `pipeline`)]' --output table
```

---

## Python (Boto3) Examples

### Production-Ready — Publish with Error Handling

```python
import json
import logging
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
sns = boto3.client("sns")


def publish_pipeline_event(
    topic_arn: str,
    pipeline: str,
    status: str,
    run_id: str,
    details: dict | None = None,
    severity: str = "info",
) -> str:
    payload = {
        "pipeline": pipeline,
        "status": status,
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **(details or {}),
    }
    try:
        resp = sns.publish(
            TopicArn=topic_arn,
            Subject=f"[{severity.upper()}] {pipeline}: {status}",
            Message=json.dumps(payload, default=str),
            MessageAttributes={
                "pipeline": {"DataType": "String", "StringValue": pipeline},
                "status": {"DataType": "String", "StringValue": status},
                "severity": {"DataType": "String", "StringValue": severity},
            },
        )
        logger.info("Published SNS message %s to %s", resp["MessageId"], topic_arn)
        return resp["MessageId"]
    except ClientError:
        logger.exception("Failed to publish to SNS topic %s", topic_arn)
        raise
```

---

### Ensure Topic Exists (Idempotent Create)

```python
import boto3
from botocore.exceptions import ClientError


def ensure_topic(name: str, kms_key_id: str | None = None) -> str:
    sns = boto3.client("sns")
    resp = sns.create_topic(Name=name)
    topic_arn = resp["TopicArn"]

    if kms_key_id:
        sns.set_topic_attributes(
            TopicArn=topic_arn,
            AttributeName="KmsMasterKeyId",
            AttributeValue=kms_key_id,
        )
    return topic_arn
```

---

### Subscribe SQS with Filter Policy

```python
import json

import boto3


def subscribe_sqs_with_filter(
    topic_arn: str,
    queue_arn: str,
    filter_statuses: list[str],
    raw_delivery: bool = True,
) -> str:
    sns = boto3.client("sns")
    resp = sns.subscribe(
        TopicArn=topic_arn,
        Protocol="sqs",
        Endpoint=queue_arn,
        Attributes={
            "FilterPolicy": json.dumps({"status": filter_statuses}),
            "RawMessageDelivery": str(raw_delivery).lower(),
        },
    )
    return resp["SubscriptionArn"]
```

---

### Batch Publish (Multiple Pipeline Results)

```python
import json

import boto3


def publish_batch_results(topic_arn: str, results: list[dict]) -> list[str]:
    sns = boto3.client("sns")
    message_ids = []
    for result in results:
        resp = sns.publish(
            TopicArn=topic_arn,
            Message=json.dumps(result),
            MessageAttributes={
                "pipeline": {
                    "DataType": "String",
                    "StringValue": result.get("pipeline", "unknown"),
                },
                "status": {
                    "DataType": "String",
                    "StringValue": result.get("status", "UNKNOWN"),
                },
            },
        )
        message_ids.append(resp["MessageId"])
    return message_ids
```

---

### Unsubscribe Stale Endpoints

```python
import boto3


def cleanup_pending_subscriptions(topic_arn: str, max_age_days: int = 7) -> int:
    sns = boto3.client("sns")
    removed = 0
    subs = sns.list_subscriptions_by_topic(TopicArn=topic_arn)["Subscriptions"]
    for sub in subs:
        if sub["SubscriptionArn"] == "PendingConfirmation":
            sns.unsubscribe(SubscriptionArn=sub["SubscriptionArn"])
            removed += 1
    return removed
```

---

### Lambda Handler — Format SNS for Slack Webhook

```python
import json
import urllib.request


def lambda_handler(event, context):
    for record in event["Records"]:
        sns_message = json.loads(record["Sns"]["Message"])
        pipeline = sns_message.get("pipeline", "unknown")
        status = sns_message.get("status", "UNKNOWN")
        text = f"*Pipeline:* {pipeline}\n*Status:* {status}\n```{json.dumps(sns_message, indent=2)}```"

        req = urllib.request.Request(
            url="https://hooks.slack.com/services/XXX",
            data=json.dumps({"text": text}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req)
    return {"statusCode": 200}
```

---

## Security Considerations

- Use **topic-specific IAM policies** limiting publish to orchestration roles.
- Redact secrets from exception tracebacks before publishing to SNS.
- Enable **CloudTrail data events** for sensitive alert topics.
- Validate subscription endpoints against an allowlist in automation scripts.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `AuthorizationError` | IAM deny on publish | Add `sns:Publish` for topic ARN |
| `KMSAccessDenied` | SNS cannot use CMK | Update KMS key policy for SNS service |
| Duplicate alerts | Retries without dedup | Use FIFO topic or idempotent consumers |
| Large message rejected | >256 KB payload | Store payload in S3; publish reference URL |

---

## Best Practices

- Include **run_id** and **CloudWatch log link** in every failure notification.
- Use **severity** message attributes for filter-based routing to PagerDuty vs. email.
- Wrap publish calls in try/except so alerting failures do not fail the primary ETL job.
- Version your **message contract** and document breaking changes for subscribers.
