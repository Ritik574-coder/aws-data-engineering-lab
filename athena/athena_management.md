# Athena — Management

## Service Overview

Athena management covers **workgroups**, **data catalogs**, **named queries**, **engine versions**, and account-level settings. Workgroups are the primary control plane for cost isolation, IAM scoping, and query result configuration in production data platforms.

**Common use cases:**
- Separate dev/staging/prod workgroups with different scan limits
- Enforce encrypted query output locations per team
- Register federated or Lambda data catalogs for hybrid queries
- Manage saved queries for BI tools and operational runbooks

**When to use it:** Before running production queries — configure workgroups, output buckets, and engine settings to prevent runaway costs and enforce security baselines.

---

## AWS CLI Commands

### List Workgroups

**Purpose:** Enumerate configured workgroups and their states.

**Command:**

```bash
aws athena list-work-groups --max-results 50
```

**Example Output (abbreviated):**

```json
{
    "WorkGroups": [
        {
            "Name": "primary-analytics",
            "State": "ENABLED",
            "Description": "Production analytics team",
            "CreationTime": "2025-01-15T10:00:00.000+00:00"
        },
        {
            "Name": "sandbox-dev",
            "State": "ENABLED",
            "Description": "Developer ad-hoc queries"
        }
    ]
}
```

---

### Get Workgroup Configuration

**Purpose:** Inspect scan limits, output location, and encryption settings.

**Command:**

```bash
aws athena get-work-group --work-group primary-analytics
```

**Example Output (abbreviated):**

```json
{
    "WorkGroup": {
        "Name": "primary-analytics",
        "Configuration": {
            "ResultConfiguration": {
                "OutputLocation": "s3://athena-query-results-prod/account-id/",
                "EncryptionConfiguration": {
                    "EncryptionOption": "SSE_KMS",
                    "KmsKey": "arn:aws:kms:us-east-1:123456789012:key/abcd1234-..."
                }
            },
            "EnforceWorkGroupConfiguration": true,
            "PublishCloudWatchMetricsEnabled": true,
            "BytesScannedCutoffPerQuery": 10737418240,
            "RequesterPaysEnabled": false,
            "EngineVersion": {"SelectedEngineVersion": "AUTO"}
        }
    }
}
```

---

### Create Workgroup

**Purpose:** Provision an isolated query environment with cost and security controls.

**Command:**

```bash
aws athena create-work-group \
  --name primary-analytics \
  --description "Production analytics — 10 GB scan limit" \
  --configuration '{
    "ResultConfiguration": {
      "OutputLocation": "s3://athena-query-results-prod/account-id/",
      "EncryptionConfiguration": {
        "EncryptionOption": "SSE_KMS",
        "KmsKey": "arn:aws:kms:us-east-1:123456789012:key/abcd1234-5678-90ab-cdef-1234567890ab"
      }
    },
    "EnforceWorkGroupConfiguration": true,
    "PublishCloudWatchMetricsEnabled": true,
    "BytesScannedCutoffPerQuery": 10737418240,
    "EngineVersion": {"SelectedEngineVersion": "AUTO"}
  }' \
  --tags Key=Environment,Value=prod Key=Team,Value=analytics
```

**Example Output:**

```json
{
    "WorkGroup": {
        "Name": "primary-analytics"
    }
}
```

---

### Update Workgroup

**Purpose:** Adjust scan limits or output location without recreating the workgroup.

**Command:**

```bash
aws athena update-work-group \
  --work-group sandbox-dev \
  --configuration-updates '{
    "ResultConfigurationUpdates": {
      "OutputLocation": "s3://athena-query-results-dev/account-id/",
      "EncryptionConfiguration": {"EncryptionOption": "SSE_S3"}
    },
    "BytesScannedCutoffPerQuery": 1073741824,
    "PublishCloudWatchMetricsEnabled": true,
    "EnforceWorkGroupConfiguration": true
  }'
```

---

### Delete Workgroup

**Purpose:** Remove an unused workgroup (must have no running queries).

**Command:**

```bash
aws athena delete-work-group --work-group old-sandbox --recursive-delete-option
```

---

### List Data Catalogs

**Purpose:** View available catalogs (AWS Data Catalog, Lambda federated catalogs).

**Command:**

```bash
aws athena list-data-catalogs
```

**Example Output:**

```json
{
    "DataCatalogsSummary": [
        {"CatalogName": "AwsDataCatalog", "Type": "LAMBDA", "Status": "CREATED"},
        {"CatalogName": "rds-federated", "Type": "LAMBDA", "Status": "CREATED"}
    ]
}
```

---

### Create Federated Data Catalog

**Purpose:** Register a Lambda-based connector catalog for RDS/DynamoDB queries.

**Command:**

```bash
aws athena create-data-catalog \
  --name rds-federated \
  --type LAMBDA \
  --description "Federated queries to operational Postgres" \
  --parameters '{
    "function": "arn:aws:lambda:us-east-1:123456789012:function:AthenaPostgreSQLConnector"
  }' \
  --tags Key=Environment,Value=prod
```

---

### List and Manage Named Queries

**Purpose:** CRUD for saved SQL templates.

**Command:**

```bash
# List
aws athena list-named-queries --work-group primary-analytics

# Get
aws athena get-named-query --named-query-id 12345678-abcd-efgh-ijkl-1234567890ab

# Delete
aws athena delete-named-query --named-query-id 12345678-abcd-efgh-ijkl-1234567890ab
```

---

### Tag Workgroup

**Purpose:** Apply cost allocation tags.

**Command:**

```bash
aws athena tag-resource \
  --resource-arn arn:aws:athena:us-east-1:123456789012:workgroup/primary-analytics \
  --tags Key=CostCenter,Value=DE-100 Key=Team,Value=analytics
```

---

## Advanced Commands

### Get Engine Versions

```bash
aws athena list-engine-versions \
  --query 'EngineVersions[].{Version:EffectiveEngineVersion,Supported:SupportedVersions}' \
  --output table
```

### Batch Get Query Execution Details

```bash
aws athena batch-get-query-execution \
  --query-execution-ids \
    a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
    b2c3d4e5-f6a7-8901-bcde-f12345678901 \
  --query 'QueryExecutions[].{Id:QueryExecutionId,State:Status.State,Scanned:Statistics.DataScannedInBytes}' \
  --output table
```

### Workgroup CloudWatch Metrics (via CLI describe)

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Athena \
  --metric-name ProcessedBytes \
  --dimensions Name=WorkGroup,Value=primary-analytics \
  --start-time 2025-03-01T00:00:00Z \
  --end-time 2025-03-02T00:00:00Z \
  --period 3600 \
  --statistics Sum
```

### Export Workgroup Config for IaC

```bash
aws athena get-work-group --work-group primary-analytics \
  --query 'WorkGroup.Configuration' --output json > workgroup-primary-analytics.json
```

---

## Python Boto3 Examples

### Basic — Create Sandbox Workgroup

```python
import boto3

athena = boto3.client("athena")

athena.create_work_group(
    Name="sandbox-dev",
    Description="Developer workgroup with 1 GB scan limit",
    Configuration={
        "ResultConfiguration": {
            "OutputLocation": "s3://athena-query-results-dev/account-id/",
            "EncryptionConfiguration": {"EncryptionOption": "SSE_S3"},
        },
        "EnforceWorkGroupConfiguration": True,
        "BytesScannedCutoffPerQuery": 1_073_741_824,
        "PublishCloudWatchMetricsEnabled": True,
    },
    Tags=[{"Key": "Environment", "Value": "dev"}],
)
```

### Production-Ready — Workgroup Provisioner

```python
import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def ensure_workgroup(
    name: str,
    output_location: str,
    scan_limit_bytes: int,
    kms_key_arn: str | None = None,
) -> None:
    athena = boto3.client("athena")

    encryption: dict[str, Any] = {"EncryptionOption": "SSE_S3"}
    if kms_key_arn:
        encryption = {"EncryptionOption": "SSE_KMS", "KmsKey": kms_key_arn}

    config = {
        "ResultConfiguration": {
            "OutputLocation": output_location,
            "EncryptionConfiguration": encryption,
        },
        "EnforceWorkGroupConfiguration": True,
        "BytesScannedCutoffPerQuery": scan_limit_bytes,
        "PublishCloudWatchMetricsEnabled": True,
        "EngineVersion": {"SelectedEngineVersion": "AUTO"},
    }

    try:
        athena.create_work_group(Name=name, Configuration=config)
        logger.info("Created workgroup %s", name)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "InvalidRequestException":
            raise
        athena.update_work_group(
            WorkGroup=name,
            ConfigurationUpdates={
                "ResultConfigurationUpdates": config["ResultConfiguration"],
                "BytesScannedCutoffPerQuery": scan_limit_bytes,
                "PublishCloudWatchMetricsEnabled": True,
                "EnforceWorkGroupConfiguration": True,
            },
        )
        logger.info("Updated existing workgroup %s", name)
```

### Audit Recent Query Costs

```python
import boto3


def audit_workgroup_queries(workgroup: str, limit: int = 20) -> list[dict]:
    athena = boto3.client("athena")
    ids = athena.list_query_executions(WorkGroup=workgroup, MaxResults=limit)["QueryExecutionIds"]

    details = athena.batch_get_query_execution(QueryExecutionIds=ids)["QueryExecutions"]
    report = []
    for q in details:
        stats = q.get("Statistics", {})
        report.append({
            "id": q["QueryExecutionId"],
            "state": q["Status"]["State"],
            "scanned_mb": round(int(stats.get("DataScannedInBytes", 0)) / 1e6, 2),
            "runtime_ms": stats.get("TotalExecutionTimeInMillis", 0),
            "sql_preview": q["Query"][:120],
        })
    return sorted(report, key=lambda x: x["scanned_mb"], reverse=True)
```

---

## Security Considerations

- Set **`EnforceWorkGroupConfiguration: true`** so users cannot override output location or encryption.
- Use **dedicated KMS keys** per environment for query result encryption.
- Scope IAM policies to specific workgroup ARNs: `arn:aws:athena:region:account:workgroup/name`.
- Block public access on **query results buckets**; apply bucket policies denying non-TLS access.
- Use **Lake Formation** alongside workgroups for table-level authorization.
- Enable **CloudTrail** logging for `CreateWorkGroup`, `UpdateWorkGroup`, and `DeleteWorkGroup`.

---

## Troubleshooting

| Error / Symptom | Root Cause | Resolution |
|-----------------|------------|------------|
| `InvalidRequestException` on create | Workgroup name exists | Use `update-work-group` instead |
| Queries fail with output error | Workgroup role lacks S3/KMS | Fix workgroup execution role or bucket policy |
| Scan limit exceeded | `BytesScannedCutoffPerQuery` hit | Optimize query or raise limit temporarily |
| Federated catalog `FAILED` | Lambda connector error | Check connector CloudWatch logs and VPC config |
| Metrics missing | `PublishCloudWatchMetricsEnabled` false | Enable in workgroup configuration |
| Cannot delete workgroup | Named queries still attached | Use `--recursive-delete-option` |

---

## Best Practices

- Create workgroups per **team × environment** (`analytics-prod`, `analytics-dev`).
- Set **bytes scanned cutoff**: 1 GB for dev, 10–50 GB for prod (adjust to workload).
- Use **separate S3 buckets** for query results per environment with lifecycle expiration.
- Manage workgroups via **Terraform** (`aws_athena_workgroup`) — treat CLI as operational override.
- Enable **CloudWatch metrics** on all prod workgroups for cost dashboards.
- Document **named queries** in Git; sync to Athena via CI/CD for drift control.
- Review **`batch-get-query-execution`** reports weekly for top scanners and optimization targets.
- Use **AUTO engine version** unless a specific version is required for compatibility testing.
