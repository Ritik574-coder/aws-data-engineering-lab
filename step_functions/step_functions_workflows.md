# Step Functions — Workflows

## Service Overview

**AWS Step Functions** is a serverless orchestration service that coordinates distributed components into visual workflows. It supports **Standard** workflows (long-running, exactly-once) and **Express** workflows (high-volume, at-least-once, sub-minute).

**Common use cases:**
- Orchestrate Glue jobs, Lambda functions, and EMR steps in ETL pipelines
- Implement retry/catch logic for flaky data ingestion tasks
- Parallelize partition processing with Map states
- Human approval gates for data quality checks before publishing curated datasets

**When to use it:** When a data pipeline has multiple dependent steps, needs built-in error handling, or requires auditable execution history — prefer Step Functions over chaining Lambda invocations manually.

---

## AWS CLI Commands

### List State Machines

```bash
aws stepfunctions list-state-machines
```

**Example Output:**

```json
{
    "stateMachines": [
        {
            "stateMachineArn": "arn:aws:states:us-east-1:123456789012:stateMachine:orders-etl-pipeline",
            "name": "orders-etl-pipeline",
            "type": "STANDARD",
            "creationDate": "2025-01-15T10:00:00+00:00"
        }
    ]
}
```

---

### Create State Machine

**Purpose:** Deploy an ETL workflow from Amazon States Language (ASL) definition.

**Command:**

```bash
aws stepfunctions create-state-machine \
  --name orders-etl-pipeline \
  --definition file://orders-etl.asl.json \
  --role-arn arn:aws:iam::123456789012:role/StepFunctionsExecutionRole \
  --type STANDARD \
  --logging-configuration '{
    "level": "ALL",
    "includeExecutionData": true,
    "destinations": [{
      "cloudWatchLogsLogGroup": {
        "logGroupArn": "arn:aws:logs:us-east-1:123456789012:log-group:/aws/states/orders-etl:*"
      }
    }]
  }'
```

**Parameters:**
| Flag | Description |
|------|-------------|
| `--type` | `STANDARD` or `EXPRESS` |
| `--definition` | ASL JSON (inline or file) |
| `--role-arn` | IAM role Step Functions assumes to invoke services |

---

### Start Execution

**Purpose:** Trigger a pipeline run with input payload.

**Command:**

```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:123456789012:stateMachine:orders-etl-pipeline \
  --name "orders-2025-03-01-$(date +%s)" \
  --input '{"date": "2025-03-01", "source_prefix": "orders/raw/"}'
```

---

### Describe Execution

```bash
aws stepfunctions describe-execution \
  --execution-arn arn:aws:states:us-east-1:123456789012:execution:orders-etl-pipeline:orders-2025-03-01-1710000000
```

**Example Output (truncated):**

```json
{
    "executionArn": "arn:aws:states:...",
    "stateMachineArn": "arn:aws:states:...",
    "name": "orders-2025-03-01-1710000000",
    "status": "RUNNING",
    "startDate": "2025-03-01T02:00:00+00:00",
    "input": "{\"date\": \"2025-03-01\"}"
}
```

---

### List Executions

```bash
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:us-east-1:123456789012:stateMachine:orders-etl-pipeline \
  --status-filter FAILED \
  --max-results 20
```

**Status values:** `RUNNING`, `SUCCEEDED`, `FAILED`, `TIMED_OUT`, `ABORTED`

---

### Get Execution History

**Purpose:** Debug failed steps and inspect state transitions.

```bash
aws stepfunctions get-execution-history \
  --execution-arn arn:aws:states:us-east-1:123456789012:execution:orders-etl-pipeline:orders-2025-03-01-1710000000 \
  --max-results 100 \
  --reverse-order
```

---

### Stop Execution

```bash
aws stepfunctions stop-execution \
  --execution-arn arn:aws:states:us-east-1:123456789012:execution:orders-etl-pipeline:orders-2025-03-01-1710000000 \
  --cause "Data quality gate failed — aborting publish"
```

---

### Update State Machine

```bash
aws stepfunctions update-state-machine \
  --state-machine-arn arn:aws:states:us-east-1:123456789012:stateMachine:orders-etl-pipeline \
  --definition file://orders-etl-v2.asl.json
```

---

## Advanced Commands

### Sample ASL — Glue Job Chain

`orders-etl.asl.json`:

```json
{
  "Comment": "Orders ETL: extract → transform → load",
  "StartAt": "RunGlueExtract",
  "States": {
    "RunGlueExtract": {
      "Type": "Task",
      "Resource": "arn:aws:states:::glue:startJobRun.sync",
      "Parameters": {
        "JobName": "orders-extract",
        "Arguments": {
          "--date.$": "$.date"
        }
      },
      "Retry": [{
        "ErrorEquals": ["States.TaskFailed", "Glue.ConcurrentRunsExceededException"],
        "IntervalSeconds": 60,
        "MaxAttempts": 3,
        "BackoffRate": 2
      }],
      "Catch": [{
        "ErrorEquals": ["States.ALL"],
        "Next": "NotifyFailure"
      }],
      "Next": "RunGlueTransform"
    },
    "RunGlueTransform": {
      "Type": "Task",
      "Resource": "arn:aws:states:::glue:startJobRun.sync",
      "Parameters": {
        "JobName": "orders-transform",
        "Arguments": {
          "--date.$": "$.date"
        }
      },
      "Next": "PublishSuccess"
    },
    "PublishSuccess": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "arn:aws:sns:us-east-1:123456789012:pipeline-alerts",
        "Message.$": "States.Format('Orders ETL succeeded for {}', $.date)"
      },
      "End": true
    },
    "NotifyFailure": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "arn:aws:sns:us-east-1:123456789012:pipeline-alerts",
        "Message": "Orders ETL failed — check Step Functions console"
      },
      "End": true
    }
  }
}
```

### Map State for Parallel Partition Processing

Use `Map` state with `MaxConcurrency` to process date partitions in parallel while capping Glue concurrent runs.

### JMESPath Query on Executions

```bash
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:us-east-1:123456789012:stateMachine:orders-etl-pipeline \
  --query 'executions[?status==`FAILED`].[name,startDate]' \
  --output table
```

### Tag State Machine

```bash
aws stepfunctions tag-resource \
  --resource-arn arn:aws:states:us-east-1:123456789012:stateMachine:orders-etl-pipeline \
  --tags Key=Team,Value=DataEngineering Key=Pipeline,Value=orders
```

---

## Python Boto3 Examples

See [step_functions_python_examples.md](step_functions_python_examples.md) for full examples.

---

## Security Considerations

- Execution role needs least-privilege permissions for each integrated service (Glue, Lambda, SNS).
- Enable **CloudWatch Logs** with `includeExecutionData: false` in production if payloads contain PII.
- Use **IAM policies** scoped to specific state machine ARNs for `StartExecution`.
- Encrypt state machine definitions containing sensitive ARNs via deployment pipelines, not hardcoded secrets.
- For cross-account workflows, use resource-based policies and explicit role assumption.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `ExecutionAlreadyExists` | Duplicate execution name | Use unique names (timestamp/UUID suffix) |
| `States.TaskFailed` | Downstream service error | Check execution history for `Cause` field |
| `AccessDeniedException` | Execution role missing permission | Add IAM policy for Glue/Lambda/S3 actions |
| Workflow stuck in RUNNING | `.sync` integration waiting | Check Glue job status; verify job completes |
| `InvalidDefinition` | ASL syntax error | Validate in Step Functions console or with `aws stepfunctions validate-state-machine-definition` |
| Express workflow lost history | 90-day limit / no full history | Use Standard for audit requirements |

---

## Best Practices

- **Use `.sync` integrations** for Glue and EMR — Step Functions waits for job completion automatically.
- **Name executions meaningfully** — include pipeline name, date partition, and run ID.
- **Implement Catch states** — route failures to SNS/PagerDuty with execution ARN in the message.
- **Set timeouts** on Task states — prevent runaway Glue jobs from blocking the workflow indefinitely.
- **Prefer Standard workflows** for batch ETL; use Express for high-frequency micro-orchestration.
- **Version definitions** — store ASL in Git; deploy via CI/CD or CloudFormation.
- **Use Map state** for fan-out over S3 prefixes or date ranges instead of sequential loops.
- **Monitor with CloudWatch alarms** on `ExecutionsFailed` metric per state machine.
