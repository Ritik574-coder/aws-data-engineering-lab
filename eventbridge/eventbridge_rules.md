# EventBridge — Rules and Event Buses

## Service Overview

**Amazon EventBridge** is a serverless event bus that connects application components using events. It replaces CloudWatch Events for new workloads and adds cross-account routing, schema registry, and partner event sources.

**Common use cases:**
- Trigger Lambda, Step Functions, or SQS when S3 objects land in a data lake
- Schedule Glue crawlers, EMR steps, or batch jobs on a cron
- Route pipeline status events to SNS or Slack via API destinations
- Fan-out domain events across microservices and analytics pipelines

**When to use it:** When you need decoupled, event-driven orchestration with filtering, scheduling, or multi-target delivery — especially for data pipeline triggers and observability hooks.

---

## AWS CLI Commands

### List Event Buses

**Purpose:** Discover default and custom event buses in the account.

**Command:**

```bash
aws events list-event-buses
```

**Example Output:**

```json
{
    "EventBuses": [
        {
            "Name": "default",
            "Arn": "arn:aws:events:us-east-1:123456789012:event-bus/default"
        },
        {
            "Name": "data-pipeline-bus",
            "Arn": "arn:aws:events:us-east-1:123456789012:event-bus/data-pipeline-bus"
        }
    ]
}
```

**Required IAM:** `events:ListEventBuses`

---

### Create a Custom Event Bus

**Purpose:** Isolate events for a team or domain (e.g., analytics pipelines).

**Command:**

```bash
aws events create-event-bus --name data-pipeline-bus
```

---

### Put Rule (Event Pattern)

**Purpose:** Match S3 object-created events and route to a Lambda target.

**Command:**

```bash
aws events put-rule \
  --name s3-raw-landing-trigger \
  --event-pattern '{
    "source": ["aws.s3"],
    "detail-type": ["Object Created"],
    "detail": {
      "bucket": {"name": ["my-data-lake-raw"]},
      "object": {"key": [{"prefix": "orders/"}]}
    }
  }' \
  --state ENABLED \
  --description "Trigger ETL when new order files land in raw zone"
```

**Parameters:**
| Flag | Description |
|------|-------------|
| `--schedule-expression` | Cron or rate (mutually exclusive with `--event-pattern`) |
| `--event-bus-name` | Custom bus name (default: `default`) |
| `--state` | `ENABLED` or `DISABLED` |

---

### Put Rule (Schedule)

**Purpose:** Run a nightly Glue crawler on a cron schedule.

**Command:**

```bash
aws events put-rule \
  --name nightly-glue-crawler \
  --schedule-expression "cron(0 2 * * ? *)" \
  --state ENABLED \
  --description "Start Glue crawler at 02:00 UTC daily"
```

**Schedule examples:**
| Expression | Meaning |
|------------|---------|
| `rate(5 minutes)` | Every 5 minutes |
| `cron(0 12 * * ? *)` | Daily at 12:00 UTC |
| `cron(0 0 ? * MON *)` | Every Monday at midnight UTC |

---

### Add Target to Rule

**Purpose:** Send matched events to Lambda, SQS, Step Functions, etc.

**Command:**

```bash
aws events put-targets \
  --rule s3-raw-landing-trigger \
  --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:123456789012:function:process-raw-orders"
```

**For SQS with dead-letter handling:**

```bash
aws events put-targets \
  --rule pipeline-failure-alert \
  --targets file://targets.json
```

`targets.json`:

```json
[
  {
    "Id": "sqs-dlq-pipeline",
    "Arn": "arn:aws:sqs:us-east-1:123456789012:pipeline-alerts",
    "DeadLetterConfig": {
      "Arn": "arn:aws:sqs:us-east-1:123456789012:pipeline-alerts-dlq"
    }
  }
]
```

---

### Put Events (Custom Events)

**Purpose:** Publish a custom event to trigger downstream pipelines.

**Command:**

```bash
aws events put-events \
  --entries '[
    {
      "Source": "com.mycompany.etl",
      "DetailType": "PipelineCompleted",
      "Detail": "{\"pipeline\":\"orders-daily\",\"status\":\"SUCCESS\",\"rows\":1500000}",
      "EventBusName": "data-pipeline-bus"
    }
  ]'
```

---

### List Rules and Describe Rule

```bash
aws events list-rules --event-bus-name data-pipeline-bus

aws events describe-rule --name s3-raw-landing-trigger
```

---

### Enable / Disable Rule

```bash
aws events disable-rule --name s3-raw-landing-trigger
aws events enable-rule --name s3-raw-landing-trigger
```

---

### Delete Rule and Targets

**Purpose:** Clean up rules (targets must be removed first).

```bash
aws events remove-targets --rule s3-raw-landing-trigger --ids "1"
aws events delete-rule --name s3-raw-landing-trigger
```

---

## Advanced Commands

### JMESPath Filtering

```bash
aws events list-rules \
  --query 'Rules[?State==`ENABLED`].[Name,ScheduleExpression,Description]' \
  --output table
```

### Cross-Account Event Bus Policy

**Purpose:** Allow a producer account to put events on a shared bus.

```bash
aws events put-permission \
  --event-bus-name data-pipeline-bus \
  --action events:PutEvents \
  --principal 987654321098 \
  --statement-id AllowProducerAccount
```

### Archive and Replay

**Purpose:** Store events for replay during pipeline recovery.

```bash
# Create archive
aws events create-archive \
  --archive-name pipeline-events-archive \
  --event-source-arn arn:aws:events:us-east-1:123456789012:event-bus/data-pipeline-bus \
  --retention-days 30

# Replay archived events to a rule
aws events start-replay \
  --replay-name recover-missed-events \
  --event-source-arn arn:aws:events:us-east-1:123456789012:event-bus/data-pipeline-bus \
  --event-start-time 2025-03-01T00:00:00Z \
  --event-end-time 2025-03-01T06:00:00Z \
  --destination '{
    "Arn": "arn:aws:events:us-east-1:123456789012:rule/data-pipeline-bus/reprocess-rule"
  }'
```

### Input Transformer

**Purpose:** Shape event payload before delivery to target.

```bash
aws events put-targets \
  --rule s3-raw-landing-trigger \
  --targets '[{
    "Id": "1",
    "Arn": "arn:aws:lambda:us-east-1:123456789012:function:process-raw-orders",
    "InputTransformer": {
      "InputPathsMap": {
        "bucket": "$.detail.bucket.name",
        "key": "$.detail.object.key"
      },
      "InputTemplate": "{\"s3_uri\": \"s3://<bucket>/<key>\"}"
    }
  }]'
```

### Pagination

```bash
aws events list-rules --max-items 50
aws events list-rules --starting-token <NextToken>
```

---

## Python Boto3 Examples

See [eventbridge_python_examples.md](eventbridge_python_examples.md) for full production examples.

**Quick reference:**

```python
import boto3

events = boto3.client("events")
events.put_events(
    Entries=[{
        "Source": "com.mycompany.etl",
        "DetailType": "PipelineCompleted",
        "Detail": '{"pipeline": "orders-daily", "status": "SUCCESS"}',
        "EventBusName": "data-pipeline-bus",
    }]
)
```

---

## Security Considerations

- Scope IAM policies to specific rule ARNs and event bus ARNs — avoid `events:*` on `*`.
- Use **resource-based policies** on custom buses for cross-account access; require `aws:PrincipalOrgID` or external ID conditions.
- Enable **CloudTrail** for `PutEvents`, `PutRule`, and `PutTargets` to audit pipeline triggers.
- Restrict who can create schedule rules — cron triggers can invoke costly Glue/EMR jobs.
- Encrypt sensitive data in event `Detail` payloads; EventBridge does not encrypt custom event content at rest beyond standard AWS protections.
- Use **dead-letter queues (DLQ)** on targets to capture failed deliveries.

**Least-privilege IAM example:**

```json
{
  "Effect": "Allow",
  "Action": ["events:PutEvents"],
  "Resource": "arn:aws:events:us-east-1:123456789012:event-bus/data-pipeline-bus"
}
```

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `ResourceNotFoundException` | Rule or bus does not exist | Verify name and region; custom buses require `--event-bus-name` |
| `FailedEntryCount > 0` on PutEvents | Invalid entry schema | Check `Source`, `DetailType`, and JSON `Detail`; max 256 KB per entry |
| Target not invoked | Missing invoke permission | Add Lambda resource policy or SQS queue policy for `events.amazonaws.com` |
| Rule never matches | Incorrect event pattern | Use EventBridge schema registry or sample events from CloudTrail |
| `LimitExceededException` | Too many rules/targets | Request quota increase; consolidate rules with broader patterns + filter in target |
| Scheduled rule skipped | Rule disabled or bus mismatch | Confirm `--state ENABLED` and correct bus |

**Debug tip:** Use CloudWatch metrics `Invocations`, `FailedInvocations`, and `TriggeredRules` for the rule.

---

## Best Practices

- **One bus per domain** — separate `data-pipeline-bus` from application events for clearer IAM boundaries.
- **Use event patterns over broad rules** — filter at the bus to reduce unnecessary Lambda invocations and cost.
- **Idempotent consumers** — S3 and custom events may duplicate; design targets to handle retries.
- **Prefer Step Functions for multi-step pipelines** — EventBridge triggers the workflow; Step Functions handles state.
- **Archive critical event streams** — enables replay after downstream outages without re-ingesting source data.
- **Tag rules** — `Environment`, `Team`, `Pipeline` for cost and ownership tracking.
- **Validate cron expressions** — use the EventBridge console scheduler preview before production deployment.
- **Monitor DLQs** — alert on DLQ depth for pipeline failure visibility.
