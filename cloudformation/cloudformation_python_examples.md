# CloudFormation — Python Boto3 Examples

## Service Overview

The Boto3 `cloudformation` client enables programmatic stack creation, change set management, event monitoring, and drift detection.

---

## Basic Examples

### Session and Client

```python
import boto3

session = boto3.Session(profile_name="data-engineer", region_name="us-east-1")
cfn = session.client("cloudformation")
```

### Describe Stack Status

```python
response = cfn.describe_stacks(StackName="data-lake-foundation")
stack = response["Stacks"][0]
print(stack["StackStatus"], stack.get("StackStatusReason", ""))
```

### List Stack Outputs

```python
response = cfn.describe_stacks(StackName="data-lake-foundation")
outputs = {o["OutputKey"]: o["OutputValue"] for o in stack["Outputs"]}
print(outputs.get("RawBucketArn"))
```

---

## Production-Ready Examples

### Create Stack and Wait

```python
import logging
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

TERMINAL = {
    "CREATE_COMPLETE", "CREATE_FAILED", "ROLLBACK_COMPLETE",
    "UPDATE_COMPLETE", "UPDATE_ROLLBACK_COMPLETE",
    "DELETE_COMPLETE", "DELETE_FAILED",
}


def create_stack_and_wait(
    cfn_client,
    stack_name: str,
    template_path: str,
    parameters: list[dict] | None = None,
    capabilities: list[str] | None = None,
    timeout: int = 1800,
) -> str:
    template_body = Path(template_path).read_text()

    try:
        cfn_client.create_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Parameters=parameters or [],
            Capabilities=capabilities or ["CAPABILITY_NAMED_IAM"],
            OnFailure="ROLLBACK",
            Tags=[
                {"Key": "ManagedBy", "Value": "boto3"},
            ],
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "AlreadyExistsException":
            raise ValueError(f"Stack {stack_name} already exists") from exc
        raise

    logger.info("Creating stack %s", stack_name)
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        resp = cfn_client.describe_stacks(StackName=stack_name)
        status = resp["Stacks"][0]["StackStatus"]
        if status in TERMINAL:
            if "FAILED" in status or "ROLLBACK" in status:
                events = cfn_client.describe_stack_events(StackName=stack_name)
                failed = [
                    e for e in events["StackEvents"]
                    if "FAILED" in e.get("ResourceStatus", "")
                ]
                raise RuntimeError(f"Stack {status}: {failed[:3]}")
            return status
        time.sleep(15)

    raise TimeoutError(f"Stack {stack_name} did not complete within {timeout}s")
```

### Create and Execute Change Set

```python
def deploy_change_set(
    cfn_client,
    stack_name: str,
    template_body: str,
    change_set_name: str,
) -> None:
    cfn_client.create_change_set(
        StackName=stack_name,
        ChangeSetName=change_set_name,
        TemplateBody=template_body,
        ChangeSetType="UPDATE",
        Capabilities=["CAPABILITY_NAMED_IAM"],
    )

    waiter = cfn_client.get_waiter("change_set_create_complete")
    waiter.wait(StackName=stack_name, ChangeSetName=change_set_name)

    desc = cfn_client.describe_change_set(
        StackName=stack_name,
        ChangeSetName=change_set_name,
    )
    for change in desc.get("Changes", []):
        detail = change["ResourceChange"]
        print(detail["Action"], detail["LogicalResourceId"], detail.get("Replacement"))

    if desc["Status"] == "FAILED" and "No updates" in desc.get("StatusReason", ""):
        print("No changes detected")
        return

    cfn_client.execute_change_set(
        StackName=stack_name,
        ChangeSetName=change_set_name,
    )
```

### Detect Drift

```python
def detect_drift(cfn_client, stack_name: str) -> list[dict]:
    resp = cfn_client.detect_stack_drift(StackName=stack_name)
    detection_id = resp["StackDriftDetectionId"]

    waiter = cfn_client.get_waiter("stack_drift_detection_complete")
    waiter.wait(StackName=stack_name)

    drifts = []
    paginator = cfn_client.get_paginator("describe_stack_resource_drifts")
    for page in paginator.paginate(StackName=stack_name):
        for drift in page["StackResourceDrifts"]:
            if drift["StackResourceDriftStatus"] == "MODIFIED":
                drifts.append({
                    "resource": drift["LogicalResourceId"],
                    "type": drift["ResourceType"],
                    "property_differences": drift.get("PropertyDifferences", []),
                })
    return drifts
```

---

## Error Handling

```python
from botocore.exceptions import ClientError

try:
    cfn.create_stack(StackName="test", TemplateBody="{}")
except ClientError as exc:
    code = exc.response["Error"]["Code"]
    if code == "InsufficientCapabilitiesException":
        print("Add CAPABILITY_IAM to request")
    elif code == "ValidationError":
        print(exc.response["Error"]["Message"])
    else:
        raise
```

---

## Security Considerations

- Load templates from trusted paths only — never from unvalidated user input.
- Review change set resource replacements — `Replacement: True` may cause data loss.
- Use stack policies in production to deny `UpdateStack` except from CI/CD roles.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Waiter timeout | Increase timeout; check `describe_stack_events` |
| Change set `FAILED` | Read `StatusReason`; often "No updates are to be performed" |
| Drift detection slow | Large stacks take minutes; use waiter, don't poll aggressively |

---

## Best Practices

- Use `create_change_set` + review in CI before `execute_change_set`.
- Parse stack outputs into downstream pipeline config (bucket names, role ARNs).
- Log all stack operations with stack name and change set ID for traceability.
