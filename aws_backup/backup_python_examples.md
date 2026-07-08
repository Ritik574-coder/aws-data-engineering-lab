# AWS Backup — Python Boto3 Examples

## Service Overview

The Boto3 `backup` client manages backup plans, on-demand jobs, recovery points, and restore operations programmatically.

---

## Basic Examples

### Session and Client

```python
import boto3

session = boto3.Session(profile_name="data-engineer", region_name="us-east-1")
backup = session.client("backup")
```

### Start On-Demand Backup

```python
response = backup.start_backup_job(
    BackupVaultName="data-platform-vault",
    ResourceArn="arn:aws:rds:us-east-1:123456789012:db:analytics-warehouse",
    IamRoleArn="arn:aws:iam::123456789012:role/AWSBackupServiceRole",
)
job_id = response["BackupJobId"]
print(f"Started backup job: {job_id}")
```

### List Recovery Points

```python
response = backup.list_recovery_points_by_backup_vault(
    BackupVaultName="data-platform-vault",
    ByResourceArn="arn:aws:rds:us-east-1:123456789012:db:analytics-warehouse",
)
for rp in response.get("RecoveryPoints", []):
    print(rp["RecoveryPointArn"], rp["CreationDate"], rp["Status"])
```

---

## Production-Ready Examples

### Poll Backup Job Until Complete

```python
import logging
import time

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

TERMINAL_STATES = {"COMPLETED", "FAILED", "ABORTED", "EXPIRED"}


def wait_for_backup_job(backup_client, job_id: str, timeout: int = 7200) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = backup_client.describe_backup_job(BackupJobId=job_id)
        state = resp["State"]
        logger.info("Backup job %s: %s", job_id, state)
        if state in TERMINAL_STATES:
            if state == "FAILED":
                raise RuntimeError(resp.get("StatusMessage", "Backup failed"))
            return state
        time.sleep(30)
    raise TimeoutError(f"Backup job {job_id} did not complete within {timeout}s")
```

### Find Latest Recovery Point

```python
from datetime import datetime


def get_latest_recovery_point(
    backup_client,
    vault_name: str,
    resource_arn: str,
) -> dict | None:
    paginator = backup_client.get_paginator("list_recovery_points_by_backup_vault")
    latest = None

    for page in paginator.paginate(
        BackupVaultName=vault_name,
        ByResourceArn=resource_arn,
    ):
        for rp in page.get("RecoveryPoints", []):
            if rp["Status"] != "COMPLETED":
                continue
            if latest is None or rp["CreationDate"] > latest["CreationDate"]:
                latest = rp

    return latest
```

### Audit Untagged Resources

```python
def find_unprotected_resources(backup_client) -> list[dict]:
    unprotected = []
    paginator = backup_client.get_paginator("list_protected_resources")

    for page in paginator.paginate():
        for resource in page.get("Results", []):
            if resource.get("LastBackupTime") is None:
                unprotected.append({
                    "arn": resource["ResourceArn"],
                    "type": resource["ResourceType"],
                })
    return unprotected
```

### Start Restore Job

```python
def restore_rds_instance(
    backup_client,
    recovery_point_arn: str,
    new_instance_id: str,
    role_arn: str,
    subnet_group: str,
    security_groups: list[str],
) -> str:
    metadata = {
        "DBInstanceIdentifier": new_instance_id,
        "DBInstanceClass": "db.r6g.xlarge",
        "DBSubnetGroupName": subnet_group,
        "VpcSecurityGroupIds": ",".join(security_groups),
    }

    response = backup_client.start_restore_job(
        RecoveryPointArn=recovery_point_arn,
        IamRoleArn=role_arn,
        Metadata=metadata,
    )
    return response["RestoreJobId"]
```

---

## Error Handling

```python
from botocore.exceptions import ClientError

try:
    backup.start_backup_job(
        BackupVaultName="data-platform-vault",
        ResourceArn="arn:aws:rds:us-east-1:123456789012:db:missing",
        IamRoleArn="arn:aws:iam::123456789012:role/AWSBackupServiceRole",
    )
except ClientError as exc:
    code = exc.response["Error"]["Code"]
    if code == "ResourceNotFoundException":
        print("Resource or vault not found")
    elif code == "InvalidParameterValueException":
        print("Check vault name and resource ARN")
    else:
        raise
```

---

## Security Considerations

- Run backup automation with a dedicated role — not personal IAM user credentials.
- Log restore job IDs and operators for audit compliance.
- Validate recovery point ARN before restore to prevent wrong-environment recovery.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Job stuck in RUNNING | Check `CompletionWindowMinutes` in plan; inspect service quotas |
| Empty recovery points list | Verify resource ARN and vault name match the backup plan |
| Restore fails metadata validation | Use `describe_restore_job` for `StatusMessage` details |

---

## Best Practices

- Wrap backup/restore in runbooks with explicit pre-checks (instance state, disk space).
- Emit metrics on backup job duration and failure rate to CloudWatch.
- Never automate production restores without approval gates.
