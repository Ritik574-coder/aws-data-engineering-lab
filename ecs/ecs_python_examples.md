# ECS — Python Boto3 Examples

## Service Overview

Boto3 ECS client for programmatic task launches, service management, deployment automation, and pipeline orchestration in data engineering workflows.

---

## AWS CLI Commands

### Quick Reference — Run Task

```bash
aws ecs run-task \
  --cluster data-pipeline-prod \
  --task-definition spark-etl-batch \
  --launch-type FARGATE \
  --network-configuration awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=DISABLED}
```

---

## Advanced Commands

### Filter Failed Tasks (Last 24 Hours)

```bash
aws ecs list-tasks --cluster data-pipeline-prod --desired-status STOPPED --max-items 50 | \
  jq -r '.taskArns[]' | xargs -I{} aws ecs describe-tasks --cluster data-pipeline-prod --tasks {} \
  --query 'tasks[?stoppedReason!=`null` && containers[0].exitCode!=`0`].{Task:taskArn,Reason:stoppedReason,Exit:containers[0].exitCode}'
```

---

## Python (Boto3) Examples

### Production-Ready — Run Task and Wait with Error Handling

```python
import logging
import time

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
ecs = boto3.client("ecs")


def run_fargate_etl(
    cluster: str,
    task_definition: str,
    subnets: list[str],
    security_groups: list[str],
    overrides: dict | None = None,
    timeout_sec: int = 3600,
) -> dict:
    try:
        resp = ecs.run_task(
            cluster=cluster,
            taskDefinition=task_definition,
            launchType="FARGATE",
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": subnets,
                    "securityGroups": security_groups,
                    "assignPublicIp": "DISABLED",
                }
            },
            overrides=overrides or {},
        )
    except ClientError:
        logger.exception("Failed to start ECS task")
        raise

    failures = resp.get("failures", [])
    if failures:
        raise RuntimeError(f"ECS run_task failures: {failures}")

    task_arn = resp["tasks"][0]["taskArn"]
    logger.info("Started task %s", task_arn)

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        desc = ecs.describe_tasks(cluster=cluster, tasks=[task_arn])["tasks"][0]
        status = desc["lastStatus"]
        if status == "STOPPED":
            container = desc["containers"][0]
            exit_code = container.get("exitCode")
            reason = desc.get("stoppedReason", "")
            if exit_code != 0:
                raise RuntimeError(
                    f"Task failed: exit={exit_code}, reason={reason}, "
                    f"container_reason={container.get('reason')}"
                )
            return {"task_arn": task_arn, "exit_code": exit_code, "stopped_reason": reason}
        time.sleep(10)

    ecs.stop_task(cluster=cluster, task=task_arn, reason="Timeout exceeded")
    raise TimeoutError(f"Task {task_arn} did not complete within {timeout_sec}s")
```

---

### Register Task Definition from Pipeline Config

```python
import boto3


def register_etl_task_definition(
    family: str,
    image: str,
    cpu: str,
    memory: str,
    execution_role: str,
    task_role: str,
    env: dict[str, str],
    log_group: str,
    region: str,
) -> str:
    ecs = boto3.client("ecs")
    resp = ecs.register_task_definition(
        family=family,
        networkMode="awsvpc",
        requiresCompatibilities=["FARGATE"],
        cpu=cpu,
        memory=memory,
        executionRoleArn=execution_role,
        taskRoleArn=task_role,
        containerDefinitions=[{
            "name": family,
            "image": image,
            "essential": True,
            "environment": [{"name": k, "value": v} for k, v in env.items()],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": log_group,
                    "awslogs-region": region,
                    "awslogs-stream-prefix": family,
                },
            },
        }],
    )
    return resp["taskDefinition"]["taskDefinitionArn"]
```

---

### Scale Service Desired Count (SQS Consumer)

```python
import boto3


def scale_service(cluster: str, service: str, desired_count: int) -> None:
    ecs = boto3.client("ecs")
    ecs.update_service(
        cluster=cluster,
        service=service,
        desiredCount=desired_count,
    )
```

---

### List Recent Failed Tasks

```python
import boto3
from datetime import datetime, timezone, timedelta


def list_failed_tasks(cluster: str, hours: int = 24) -> list[dict]:
    ecs = boto3.client("ecs")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    failed = []

    paginator = ecs.get_paginator("list_tasks")
    for page in paginator.paginate(cluster=cluster, desiredStatus="STOPPED"):
        if not page["taskArns"]:
            continue
        for batch_start in range(0, len(page["taskArns"]), 100):
            arns = page["taskArns"][batch_start : batch_start + 100]
            tasks = ecs.describe_tasks(cluster=cluster, tasks=arns)["tasks"]
            for task in tasks:
                stopped_at = task.get("stoppedAt")
                if stopped_at and stopped_at < cutoff:
                    continue
                exit_code = task["containers"][0].get("exitCode")
                if exit_code not in (0, None):
                    failed.append({
                        "task_arn": task["taskArn"],
                        "exit_code": exit_code,
                        "stopped_reason": task.get("stoppedReason"),
                        "started_at": task.get("startedAt"),
                    })
    return failed
```

---

### Step Functions Integration — Pass Task ARN

```python
def build_ecs_run_task_params(
    cluster: str,
    task_definition: str,
    subnets: list[str],
    security_groups: list[str],
    run_date: str,
) -> dict:
    """Return parameters dict for Step Functions ECS RunTask integration."""
    return {
        "Cluster": cluster,
        "TaskDefinition": task_definition,
        "LaunchType": "FARGATE",
        "NetworkConfiguration": {
            "AwsvpcConfiguration": {
                "Subnets": subnets,
                "SecurityGroups": security_groups,
                "AssignPublicIp": "DISABLED",
            }
        },
        "Overrides": {
            "ContainerOverrides": [{
                "Name": task_definition.split(":")[0].split("/")[-1],
                "Environment": [{"Name": "RUN_DATE", "Value": run_date}],
            }]
        },
    }
```

---

## Security Considerations

- Task roles should scope S3 prefixes with **condition keys** on bucket/prefix ARNs.
- Fetch database credentials from **Secrets Manager** via `secrets` in container definition.
- Restrict `ecs:RunTask` to specific task definition ARNs in IAM policies.
- Enable **Container Insights** for anomaly detection without shell access.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `InvalidParameterException` | CPU/memory combo invalid for Fargate | Consult Fargate valid CPU/memory matrix |
| `ServiceNotFoundException` | Wrong cluster/service name | List services with `list-services` |
| Wait loop never completes | Task in `DEPROVISIONING` | Increase poll interval; check underlying ENI cleanup |
| Throttling on `describe_tasks` | High poll frequency | Exponential backoff; use EventBridge on task state change |

---

## Best Practices

- Use **task definition families** with immutable revision numbers for rollback.
- Emit structured logs with `run_id`, `pipeline`, and `partition` fields.
- Integrate task launch into **Step Functions** for retry and catch semantics.
- Alert on failed tasks via **EventBridge** rule → SNS for on-call paging.
