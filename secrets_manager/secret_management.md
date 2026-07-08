# Secrets Manager — Secret Management

## Service Overview

**AWS Secrets Manager** helps you protect credentials, API keys, and connection strings used in data engineering pipelines. It provides centralized storage, fine-grained access control, automatic rotation, and audit logging.

**Common use cases:**
- Database credentials for Redshift, RDS, and Aurora (referenced by Glue, Lambda, EMR)
- API keys for third-party data providers (SaaS ingestion)
- JDBC/ODBC connection strings for ETL tools (Airflow, dbt)
- Redshift Data API `--secret-arn` integration
- Cross-account secret sharing for multi-account data platforms

**When to use it:** Whenever secrets would otherwise live in environment variables, parameter files, or code — especially when rotation and audit trails are required for compliance.

**Secrets Manager vs SSM Parameter Store:**
| Feature | Secrets Manager | SSM Parameter Store |
|---------|-----------------|---------------------|
| Automatic rotation | Yes (Lambda) | No (manual) |
| Cost | Per secret/month + API calls | Standard params free tier |
| Cross-account | Resource policy | Limited |
| Best for | DB creds, rotating secrets | Config, non-sensitive params |

---

## AWS CLI Commands

### Create Secret

**Purpose:** Store database credentials for a Redshift ETL service account.

**Command:**

```bash
aws secretsmanager create-secret \
  --name redshift/etl-service \
  --description "Redshift ETL service account credentials" \
  --secret-string '{"username":"etl_service","password":"CHANGE_ME","engine":"redshift","host":"analytics-dw.abc123.us-east-1.redshift.amazonaws.com","port":5439,"dbname":"analytics"}' \
  --tags Key=Environment,Value=prod Key=Team,Value=data-platform
```

**Example Output:**

```json
{
    "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:redshift/etl-service-AbCdEf",
    "Name": "redshift/etl-service",
    "VersionId": "01234567-89ab-cdef-0123-456789abcdef"
}
```

**Required IAM:** `secretsmanager:CreateSecret`

---

### Get Secret Value

**Purpose:** Retrieve credentials for pipeline validation (avoid in production scripts — use IAM role + SDK).

**Command:**

```bash
aws secretsmanager get-secret-value \
  --secret-id redshift/etl-service \
  --query '{ARN:ARN,Name:Name,Version:VersionId}' \
  --output table
```

**Retrieve secret string only:**

```bash
aws secretsmanager get-secret-value \
  --secret-id redshift/etl-service \
  --query 'SecretString' \
  --output text | jq .
```

---

### List Secrets

**Purpose:** Inventory secrets for governance and cost review.

**Command:**

```bash
aws secretsmanager list-secrets \
  --filters Key=name,Values=redshift/ \
  --query 'SecretList[].{Name:Name,ARN:ARN,LastChanged:LastChangedDate,Rotation:RotationEnabled}' \
  --output table
```

---

### Update Secret Value

**Purpose:** Rotate password manually or after DB admin change.

**Command:**

```bash
aws secretsmanager update-secret \
  --secret-id redshift/etl-service \
  --secret-string '{"username":"etl_service","password":"NEW_SECURE_PASSWORD","engine":"redshift","host":"analytics-dw.abc123.us-east-1.redshift.amazonaws.com","port":5439,"dbname":"analytics"}'
```

---

### Put Resource Policy (Cross-Account Access)

**Purpose:** Allow Glue job role in another account to read a shared secret.

**Command:**

```bash
aws secretsmanager put-resource-policy \
  --secret-id redshift/etl-service \
  --resource-policy '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::987654321098:role/GlueETLRole"},
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "*"
    }]
  }'
```

---

### Enable Automatic Rotation

**Purpose:** Rotate RDS/Redshift credentials on a schedule via Lambda.

**Command:**

```bash
aws secretsmanager rotate-secret \
  --secret-id rds/analytics-metadata \
  --rotation-lambda-arn arn:aws:lambda:us-east-1:123456789012:function:SecretsManagerRDSRotation \
  --rotation-rules AutomaticallyAfterDays=30
```

---

### Describe Secret

**Command:**

```bash
aws secretsmanager describe-secret \
  --secret-id redshift/etl-service \
  --query '{Name:Name,ARN:ARN,Rotation:RotationEnabled,LastRotated:LastRotatedDate,Tags:Tags}' \
  --output json
```

---

### Delete Secret (with Recovery Window)

**Purpose:** Soft-delete with 7–30 day recovery window.

**Command:**

```bash
aws secretsmanager delete-secret \
  --secret-id redshift/etl-service-dev \
  --recovery-window-in-days 7
```

**Force immediate delete (no recovery):**

```bash
aws secretsmanager delete-secret \
  --secret-id temp/migration-creds \
  --force-delete-without-recovery
```

---

### Restore Deleted Secret

**Command:**

```bash
aws secretsmanager restore-secret --secret-id redshift/etl-service-dev
```

---

## Advanced Commands

### Filter Secrets with JMESPath

```bash
aws secretsmanager list-secrets \
  --query 'SecretList[?RotationEnabled==`true`].{Name:Name,LastRotated:LastRotatedDate}' \
  --output table
```

### Paginate List Secrets

```bash
aws secretsmanager list-secrets --max-results 50 --starting-token "eyJ..."
```

### Get Secret Version Stages

```bash
aws secretsmanager describe-secret \
  --secret-id redshift/etl-service \
  --query 'VersionIdsToStages' \
  --output json
```

### Replicate Secret to Another Region (DR)

```bash
aws secretsmanager replicate-secret-to-regions \
  --secret-id redshift/etl-service \
  --add-replica-regions Region=us-west-2,KmsKeyId=alias/secrets-dr-key
```

### Tag Secret

```bash
aws secretsmanager tag-resource \
  --secret-id redshift/etl-service \
  --tags Key=CostCenter,Value=analytics Key=DataClassification,Value=confidential
```

### Validate Resource Policy

```bash
aws secretsmanager validate-resource-policy \
  --resource-policy file://secret-policy.json
```

---

## Python (Boto3) Examples

### Basic — Get Secret

```python
import json
import boto3

client = boto3.client("secretsmanager")
resp = client.get_secret_value(SecretId="redshift/etl-service")
creds = json.loads(resp["SecretString"])
print(creds["username"], creds["host"])
```

See [python_examples.md](python_examples.md) for caching, rotation handlers, and Glue integration.

---

## Security Considerations

- Never commit secrets to Git, CloudFormation parameters (plain text), or Glue job arguments.
- Use **least-privilege IAM**: `secretsmanager:GetSecretValue` scoped to specific secret ARNs.
- Enable **KMS encryption** with customer-managed keys (CMK) for audit and cross-account control.
- Enable **CloudTrail** logging for `GetSecretValue` to detect unauthorized access.
- Use **resource policies** for cross-account access instead of duplicating secrets.
- Prefer **IAM roles** over long-lived access keys for services retrieving secrets.
- Set **`recovery-window-in-days`** on delete to prevent accidental permanent loss.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `ResourceNotFoundException` | Wrong name/ARN or deleted secret | Verify secret ID; check `list-secrets` including deleted |
| `AccessDeniedException` | IAM or resource policy deny | Add `GetSecretValue` on secret ARN + `kms:Decrypt` on CMK |
| `InvalidRequestException` during rotation | Lambda lacks VPC/DB access | Verify rotation Lambda SG and IAM |
| Secret value is binary | Secret stored as binary | Use `SecretBinary` instead of `SecretString` |
| Stale credentials after rotation | App caches old value | Read `AWSCURRENT` stage; implement cache TTL |
| Cross-account access fails | Missing resource policy | Add principal to `put-resource-policy` |

---

## Best Practices

- Use **hierarchical naming**: `redshift/prod/etl-service`, `rds/analytics/metadata`.
- Store secrets as **JSON** with standard keys (`username`, `password`, `host`, `port`, `engine`, `dbname`).
- Enable **automatic rotation** for RDS/Redshift using AWS-provided rotation templates.
- Replicate critical secrets **cross-region** for DR workloads.
- Tag secrets with `Environment`, `Owner`, `RotationSchedule` for governance.
- Reference secrets by **ARN** in Redshift Data API, Glue connections, and Lambda env (`SECRET_ARN` only — not the value).
- Audit monthly: remove unused secrets to reduce cost ($0.40/secret/month).
- Integrate with **AWS Config** rules to detect secrets without rotation.
