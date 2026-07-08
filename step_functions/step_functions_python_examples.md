# Step Functions — Python Boto3 Examples

## Service Overview

The Boto3 `stepfunctions` client (`sfn`) lets you start executions, poll status, and manage state machines programmatically — useful for pipeline schedulers, backfill tools, and operational runbooks.

---

## Basic Examples

### Session and Client

```python
import boto3

session = boto3.Session(profile_name="data-engineer", region_name="us-east-1")
sfn = session.client("stepfunctions")
```

### Start and Poll Execution

```python
import time

STATE_MACHINE_ARN = "arn:aws:states:us-east-1:123456789012:stateMachine:orders-etl-pipeline"

response = sfn.start_execution(
    stateMachineArn=STATE_MACHINE_ARN,
    name=f"orders-2025-03-01-{int(time.time())}",
    input='{"date": "2025-03-01", "source_prefix": "orders/raw/"}',
)
execution_arn = response["executionArn"]

while True:
    desc = sfn.describe_execution(executionArn=execution_arn)
    status = desc["status"]
    if status in ("SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"):
        break
    time.sleep(10)

print(f"Final status: {status}")
if status == "FAILED":
    print(desc.get("error"), desc.get("cause"))
```

---

## Production-Ready Examples

### Pipeline Runner with Structured Logging

```python
import json
import logging
import time
import uuid
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    execution_arn: str
    status: str
    output: dict | None = None
    error: str | None = None


def run_pipeline(
    sfn_client,
    state_machine_arn: str,
    payload: dict,
    *,
    execution_name: str | None = None,
    poll_interval: int = 15,
    timeout_seconds: int = 3600,
) -> ExecutionResult:
    name = execution_name or f"run-{uuid.uuid4().hex[:12]}"
    start = time.monotonic()

    try:
        resp = sfn_client.start_execution(
            stateMachineArn=state_machine_arn,
            name=name,
            input=json.dumps(payload),
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ExecutionAlreadyExists":
            raise ValueError(f"Execution name already exists: {name}") from exc
        raise

    arn = resp["executionArn"]
    logger.info("Started execution %s", arn)

    while time.monotonic() - start < timeout_seconds:
        desc = sfn_client.describe_execution(executionArn=arn)
        status = desc["status"]
        if status != "RUNNING":
            output = None
            if "output" in desc:
                output = json.loads(desc["output"])
            return ExecutionResult(
                execution_arn=arn,
                status=status,
                output=output,
                error=desc.get("error"),
            )
        time.sleep(poll_interval)

    sfn_client.stop_execution(
        executionArn=arn,
        cause=f"Timed out after {timeout_seconds}s",
    )
    return ExecutionResult(execution_arn=arn, status="TIMED_OUT")
```

### List Failed Executions (Last 24 Hours)

```python
from datetime import datetime, timedelta, timezone

def list_recent_failures(sfn_client, state_machine_arn: str, hours: int = 24) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    failures = []
    paginator = sfn_client.get_paginator("list_executions")

    for page in paginator.paginate(
        stateMachineArn=state_machine_arn,
        statusFilter="FAILED",
    ):
        for ex in page["executions"]:
            if ex["startDate"] >= cutoff:
                failures.append({
                    "name": ex["name"],
                    "executionArn": ex["executionArn"],
                    "startDate": ex["startDate"].isoformat(),
                })
    return failures
```

### Get Failure Details from History

```python
def get_failure_cause(sfn_client, execution_arn: str) -> str | None:
    history = sfn_client.get_execution_history(
        executionArn=execution_arn,
        reverseOrder=True,
        maxResults=50,
    )
    for event in history["events"]:
        if event["type"] == "ExecutionFailed":
            detail = event["executionFailedEventDetails"]
            return f"{detail.get('error')}: {detail.get('cause')}"
        if event["type"] == "TaskFailed":
            detail = event["taskFailedEventDetails"]
            return f"{detail.get('error')}: {detail.get('cause')}"
    return None
```

### Create State Machine from Python

```python
import json

ASL_DEFINITION = {
    "Comment": "Minimal Lambda invoke",
    "StartAt": "InvokeProcessor",
    "States": {
        "InvokeProcessor": {
            "Type": "Task",
            "Resource": "arn:aws:states:::lambda:invoke",
            "Parameters": {
                "FunctionName": "process-orders",
                "Payload.$": "$",
            },
            "End": True,
        }
    },
}

sfn.create_state_machine(
    name="orders-processor",
    definition=json.dumps(ASL_DEFINITION),
    roleArn="arn:aws:iam::123456789012:role/StepFunctionsExecutionRole",
    type="STANDARD",
)
```

---

## Error Handling

```python
from botocore.exceptions import ClientError, BotoCoreError

try:
    sfn.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        name="duplicate-name",
        input="{}",
    )
except ClientError as exc:
    code = exc.response["Error"]["Code"]
    if code == "ExecutionAlreadyExists":
        print("Use a unique execution name")
    elif code == "StateMachineDoesNotExist":
        print("Verify state machine ARN and region")
    else:
        raise
except BotoCoreError:
    logger.exception("Network or credential error")
    raise
```

---

## Security Considerations

- Do not pass secrets in execution input — reference Secrets Manager ARNs and fetch in Task states.
- Restrict `states:StartExecution` to specific state machine ARNs in IAM policies.
- Sanitize execution output before logging — may contain pipeline data samples.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ExecutionAlreadyExists` | Append UUID or timestamp to execution name |
| Polling never completes | Check Glue/Lambda logs; increase Task timeout in ASL |
| Empty `output` on success | Ensure final state returns a result; check `ResultPath` |

---

## Best Practices

- Use `uuid.uuid4()` for execution names in automated backfill scripts.
- Wrap polling in timeout logic — don't block CI/CD indefinitely.
- Emit custom CloudWatch metrics from a final Lambda step for pipeline SLA tracking.
- Store ASL definitions in version control; create state machines via deployment pipeline.
