# Redshift — Python Boto3 Examples

## Service Overview

This guide covers **Boto3** patterns for Redshift cluster management, **Redshift Data API** SQL execution, and **Redshift Serverless** integration — common in Lambda, Glue, Airflow, and Step Functions pipelines.

**Clients used:**
| Client | Purpose |
|--------|---------|
| `redshift` | Cluster lifecycle, snapshots, parameter groups |
| `redshift-data` | Execute SQL without JDBC |
| `redshift-serverless` | Namespace and workgroup management |

---

## AWS CLI Commands

Reference commands for pairing with Python automation:

```bash
# Execute and wait
STATEMENT_ID=$(aws redshift-data execute-statement \
  --cluster-identifier analytics-dw \
  --database analytics \
  --secret-arn arn:aws:secretsmanager:us-east-1:123456789012:secret:redshift/etl \
  --sql "SELECT 1;" \
  --query 'Id' --output text)

aws redshift-data wait statement-finished --id "$STATEMENT_ID"
```

---

## Advanced Commands

### Export Query Results to S3 via UNLOAD (CLI-triggered)

```bash
aws redshift-data execute-statement \
  --cluster-identifier analytics-dw \
  --database analytics \
  --db-user etl_service \
  --sql "UNLOAD ('SELECT * FROM public.orders_fact WHERE order_date = ''2025-03-01''') TO 's3://analytics-exports/orders/dt=2025-03-01/' IAM_ROLE 'arn:aws:iam::123456789012:role/RedshiftUnloadRole' FORMAT AS PARQUET ALLOWOVERWRITE;"
```

---

## Python (Boto3) Examples

### Basic — Describe Cluster

```python
import boto3

client = boto3.client("redshift")
resp = client.describe_clusters(ClusterIdentifier="analytics-dw")
cluster = resp["Clusters"][0]
print(cluster["ClusterStatus"], cluster["Endpoint"]["Address"])
```

### Execute SQL and Poll Until Finished

```python
import logging
import time

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def run_sql(
    sql: str,
    cluster_id: str,
    database: str,
    secret_arn: str,
    poll_interval: float = 2.0,
    timeout: float = 600.0,
) -> str:
    """Execute SQL via Redshift Data API and wait for completion."""
    client = boto3.client("redshift-data")
    try:
        resp = client.execute_statement(
            ClusterIdentifier=cluster_id,
            Database=database,
            SecretArn=secret_arn,
            Sql=sql,
        )
    except ClientError as exc:
        logger.error("Execute failed: %s", exc.response["Error"]["Message"])
        raise

    statement_id = resp["Id"]
    deadline = time.time() + timeout

    while time.time() < deadline:
        desc = client.describe_statement(Id=statement_id)
        status = desc["Status"]
        if status == "FINISHED":
            logger.info("Statement %s finished in %sms", statement_id, desc.get("Duration", 0))
            return statement_id
        if status in ("FAILED", "ABORTED"):
            raise RuntimeError(f"Statement {statement_id} {status}: {desc.get('Error', 'unknown')}")
        time.sleep(poll_interval)

    client.cancel_statement(Id=statement_id)
    raise TimeoutError(f"Statement {statement_id} timed out after {timeout}s")
```

### Fetch Paginated Query Results

```python
import boto3


def fetch_all_results(statement_id: str) -> list[list]:
    client = boto3.client("redshift-data")
    rows = []
    next_token = None

    while True:
        kwargs = {"Id": statement_id}
        if next_token:
            kwargs["NextToken"] = next_token
        resp = client.get_statement_result(**kwargs)

        column_names = [col["name"] for col in resp["ColumnMetadata"]]
        if not rows:
            rows.append(column_names)

        for record in resp["Records"]:
            row = []
            for field in record:
                value = next(iter(field.values()), None)
                row.append(value)
            rows.append(row)

        next_token = resp.get("NextToken")
        if not next_token:
            break

    return rows
```

### Production-Ready — ETL Load Orchestrator

```python
import logging
from datetime import date

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

CLUSTER_ID = "analytics-dw"
DATABASE = "analytics"
SECRET_ARN = "arn:aws:secretsmanager:us-east-1:123456789012:secret:redshift/etl"
LOAD_ROLE = "arn:aws:iam::123456789012:role/RedshiftLoadRole"


def build_incremental_load_sql(load_date: date, s3_prefix: str) -> str:
    dt = load_date.isoformat()
    return f"""
        BEGIN;
        TRUNCATE staging.orders;
        COPY staging.orders
        FROM '{s3_prefix}'
        IAM_ROLE '{LOAD_ROLE}'
        FORMAT AS PARQUET;

        DELETE FROM public.orders_fact
        USING staging.orders s
        WHERE orders_fact.order_id = s.order_id
          AND s.order_date = '{dt}';

        INSERT INTO public.orders_fact
        SELECT order_id, customer_id, order_date, amount, updated_at
        FROM staging.orders
        WHERE order_date = '{dt}';

        ANALYZE public.orders_fact;
        COMMIT;
    """


def run_etl_load(load_date: date, s3_prefix: str) -> None:
    client = boto3.client("redshift-data")
    sql = build_incremental_load_sql(load_date, s3_prefix)

    try:
        resp = client.execute_statement(
            ClusterIdentifier=CLUSTER_ID,
            Database=DATABASE,
            SecretArn=SECRET_ARN,
            Sql=sql,
            StatementName=f"orders-load-{load_date.isoformat()}",
        )
        statement_id = resp["Id"]
        logger.info("Started ETL load statement %s", statement_id)

        waiter = client.get_waiter("statement_finished")
        waiter.wait(Id=statement_id)

        result = client.describe_statement(Id=statement_id)
        if result["Status"] != "FINISHED":
            raise RuntimeError(result.get("Error", "ETL load failed"))

        logger.info("ETL load completed in %sms", result.get("Duration", 0))
    except ClientError:
        logger.exception("Redshift Data API error")
        raise
```

### Serverless — Execute Statement

```python
import boto3

client = boto3.client("redshift-data")

resp = client.execute_statement(
    WorkgroupName="analytics-serverless",
    Database="analytics",
    SecretArn="arn:aws:secretsmanager:us-east-1:123456789012:secret:redshift/analytics-admin",
    Sql="SELECT COUNT(*) FROM public.orders_fact;",
)
print(resp["Id"])
```

### Cluster Snapshot Automation

```python
import logging
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def create_daily_snapshot(cluster_id: str) -> str:
    client = boto3.client("redshift")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_id = f"{cluster_id}-daily-{timestamp}"

    try:
        client.create_cluster_snapshot(
            ClusterIdentifier=cluster_id,
            SnapshotIdentifier=snapshot_id,
        )
        waiter = client.get_waiter("snapshot_available")
        waiter.wait(SnapshotIdentifier=snapshot_id)
        logger.info("Snapshot %s available", snapshot_id)
        return snapshot_id
    except ClientError as exc:
        logger.error("Snapshot failed: %s", exc.response["Error"]["Message"])
        raise
```

### List Load Errors After COPY

```python
import boto3


def get_recent_load_errors(cluster_id: str, database: str, secret_arn: str) -> list[dict]:
    client = boto3.client("redshift-data")
    sql = """
        SELECT query, filename, line_number, colname, err_reason, starttime
        FROM stl_load_errors
        ORDER BY starttime DESC
        LIMIT 10;
    """
    resp = client.execute_statement(
        ClusterIdentifier=cluster_id,
        Database=database,
        SecretArn=secret_arn,
        Sql=sql,
    )
    waiter = client.get_waiter("statement_finished")
    waiter.wait(Id=resp["Id"])

    result = client.get_statement_result(Id=resp["Id"])
    errors = []
    for record in result["Records"]:
        errors.append({
            "query": record[0].get("longValue"),
            "filename": record[1].get("stringValue"),
            "line_number": record[2].get("longValue"),
            "colname": record[3].get("stringValue"),
            "err_reason": record[4].get("stringValue"),
        })
    return errors
```

### Redshift Serverless — Create Workgroup

```python
import boto3

serverless = boto3.client("redshift-serverless")

serverless.create_workgroup(
    workgroupName="analytics-serverless",
    namespaceName="analytics-ns",
    baseCapacity=32,
    subnetIds=["subnet-0abc123", "subnet-0def456"],
    securityGroupIds=["sg-0abc123"],
    publiclyAccessible=False,
    tags=[{"key": "Environment", "value": "prod"}],
)
```

---

## Security Considerations

- Use **Secrets Manager** ARNs with Data API — never pass passwords in code or environment variables.
- Scope IAM policies: `redshift-data:ExecuteStatement` on specific cluster/workgroup ARNs.
- Run ETL as a **dedicated database user** with minimal privileges (staging + target schemas only).
- Log statement IDs for audit; avoid logging full SQL containing sensitive literals.
- Use **VPC endpoints** for private Data API access from Lambda in VPC.

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `ValidationException: SecretArn invalid` | Wrong ARN or region | Match secret region to Redshift cluster |
| Statement stuck `SUBMITTED` | WLM queue full | Check `stv_wlm_query_state`; tune WLM |
| Empty `get_statement_result` | DDL statement (no result set) | Use `describe_statement` for status only |
| `AccessDeniedException` on Data API | Missing IAM | Add `redshift-data:*` + `secretsmanager:GetSecretValue` |
| Connection timeout on `redshift` client | API vs JDBC confusion | Data API does not use port 5439 |

---

## Best Practices

- Use **`get_waiter("statement_finished")`** instead of manual polling when possible.
- Set **`StatementName`** for traceability in `STL_QUERY` and CloudWatch.
- Batch DDL + COPY + transform in a **single transaction** (`BEGIN`/`COMMIT`).
- Implement **retry with backoff** for transient `InternalServerException`.
- Use **Step Functions** to orchestrate: execute → wait → branch on status → notify SNS.
- Cache **column metadata** from `get_statement_result` for typed parsing.
- For high-volume metadata queries, prefer **system tables** over `information_schema`.
- Tag automated snapshots and delete aged snapshots via Lambda + EventBridge schedule.
