# AWS Backup — Backup Management

## Service Overview

**AWS Backup** is a fully managed service that centralizes backup policies across AWS services — RDS, DynamoDB, EFS, FSx, S3, and more. It replaces per-service backup cron jobs with vaults, plans, and compliance monitoring.

**Common use cases:**
- Nightly snapshots of RDS data warehouse instances
- Cross-region copy of critical database backups for DR
- Compliance retention (7 daily, 4 weekly, 12 monthly)
- Protect S3 data lake buckets with continuous or periodic backups

**When to use it:** When you need unified backup governance, cross-account/cross-region copies, or audit-ready retention policies across multiple data stores.

---

## AWS CLI Commands

### Create Backup Vault

**Purpose:** Encrypted storage container for recovery points.

**Command:**

```bash
aws backup create-backup-vault \
  --backup-vault-name data-platform-vault \
  --encryption-key-arn arn:aws:kms:us-east-1:123456789012:key/abcd1234-5678-90ef-ghij-klmnopqrstuv
```

---

### Create Backup Plan

**Purpose:** Define schedule and lifecycle for RDS and DynamoDB resources.

**Command:**

```bash
aws backup create-backup-plan --backup-plan '{
  "BackupPlanName": "data-platform-daily",
  "Rules": [{
    "RuleName": "daily-rds-retention-35d",
    "TargetBackupVaultName": "data-platform-vault",
    "ScheduleExpression": "cron(0 5 ? * * *)",
    "StartWindowMinutes": 60,
    "CompletionWindowMinutes": 180,
    "Lifecycle": {
      "DeleteAfterDays": 35
    },
    "CopyActions": [{
      "Lifecycle": {"DeleteAfterDays": 35},
      "DestinationBackupVaultArn": "arn:aws:backup:eu-west-1:123456789012:backup-vault:dr-vault"
    }]
  }]
}'
```

---

### Assign Resources to Plan

**Purpose:** Tag-based selection of RDS instances and DynamoDB tables.

**Command:**

```bash
aws backup create-backup-selection \
  --backup-plan-id <plan-id> \
  --backup-selection '{
    "SelectionName": "tagged-data-stores",
    "IamRoleArn": "arn:aws:iam::123456789012:role/AWSBackupServiceRole",
    "Resources": [],
    "ListOfTags": [{
      "ConditionType": "STRINGEQUALS",
      "ConditionKey": "Backup",
      "ConditionValue": "daily"
    }]
  }'
```

---

### Start On-Demand Backup

```bash
aws backup start-backup-job \
  --backup-vault-name data-platform-vault \
  --resource-arn arn:aws:rds:us-east-1:123456789012:db:analytics-warehouse \
  --iam-role-arn arn:aws:iam::123456789012:role/AWSBackupServiceRole
```

---

### List Recovery Points

```bash
aws backup list-recovery-points-by-backup-vault \
  --backup-vault-name data-platform-vault \
  --by-resource-arn arn:aws:rds:us-east-1:123456789012:db:analytics-warehouse
```

**Example Output:**

```json
{
    "RecoveryPoints": [
        {
            "RecoveryPointArn": "arn:aws:backup:us-east-1:123456789012:recovery-point:abc123",
            "CreationDate": "2025-03-01T05:15:00+00:00",
            "Status": "COMPLETED",
            "BackupSizeBytes": 53687091200
        }
    ]
}
```

---

### Start Restore Job

```bash
aws backup start-restore-job \
  --recovery-point-arn arn:aws:backup:us-east-1:123456789012:recovery-point:abc123 \
  --iam-role-arn arn:aws:iam::123456789012:role/AWSBackupServiceRole \
  --metadata file://rds-restore-metadata.json
```

`rds-restore-metadata.json`:

```json
{
  "DBInstanceIdentifier": "analytics-warehouse-restored",
  "DBInstanceClass": "db.r6g.xlarge",
  "VpcSecurityGroupIds": "sg-0123456789abcdef0",
  "DBSubnetGroupName": "analytics-subnet-group"
}
```

---

### Describe Backup Job

```bash
aws backup describe-backup-job --backup-job-id <job-id>
```

---

### List Backup Plans

```bash
aws backup list-backup-plans
```

---

## Advanced Commands

### Cross-Account Backup Vault Access

```bash
aws backup put-backup-vault-access-policy \
  --backup-vault-name dr-vault \
  --policy file://vault-access-policy.json
```

### Audit Backup Compliance

```bash
aws backup list-protected-resources \
  --query 'Results[?LastBackupTime==null].[ResourceArn,ResourceType]' \
  --output table
```

### EventBridge Integration — Monitor Failures

Create a rule on `aws.backup` source with `detail-type: Backup Job State Change` and `detail.state: FAILED`.

### JMESPath — Failed Jobs Last 24h

```bash
aws backup list-backup-jobs \
  --by-state FAILED \
  --max-results 50 \
  --query 'BackupJobs[*].[ResourceArn,StatusMessage,CreationDate]' \
  --output table
```

---

## Python Boto3 Examples

See [backup_python_examples.md](backup_python_examples.md).

---

## Security Considerations

- Use **dedicated KMS keys** for backup vaults — separate from application encryption keys.
- Scope `AWSBackupServiceRole` with least privilege — tag-based resource selection limits blast radius.
- Enable **vault lock** for compliance workloads (WORM retention).
- Restrict cross-account vault access with explicit vault policies and Organizations SCPs.
- Encrypt cross-region copies in transit and at rest (default with KMS).

**Required IAM for backup role:**

```json
{
  "Effect": "Allow",
  "Action": [
    "rds:CreateDBSnapshot",
    "rds:DescribeDBInstances",
    "backup:StartBackupJob",
    "backup:StopBackupJob"
  ],
  "Resource": "*",
  "Condition": {
    "StringEquals": {"aws:ResourceTag/Backup": "daily"}
  }
}
```

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| Backup job FAILED | IAM role missing service permissions | Attach AWS managed `AWSBackupServiceRolePolicyForBackup` and refine |
| Resource not in plan | Missing backup tag | Add `Backup=daily` tag or explicit resource ARN in selection |
| Cross-region copy fails | Vault policy or KMS key policy | Allow destination account on KMS key; configure vault access policy |
| Restore metadata invalid | Wrong resource-type metadata schema | Use AWS docs for RDS/DynamoDB restore metadata fields |
| `ConflictException` on vault lock | Lock already applied | Vault lock is irreversible — plan retention carefully |

---

## Best Practices

- **Tag all data stores** intended for backup (`Backup=daily`, `Environment=production`).
- **Separate vaults** by environment — dev backups should not share production vaults.
- **Test restores quarterly** — backup without tested restore is incomplete DR planning.
- **Use cross-region copy** for RDS and critical DynamoDB tables.
- **Monitor failed jobs** via EventBridge → SNS for on-call alerting.
- **Align retention with compliance** — use lifecycle rules, not indefinite retention.
- **Document RTO/RPO** per data store and map to backup plan schedules.
