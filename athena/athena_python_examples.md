# Athena — Python Boto3 Examples

## Service Overview

The Boto3 `athena` client enables programmatic query submission, workgroup management, and cost auditing from Python pipelines, notebooks, and internal data platforms. It complements the AWS CLI for integration with orchestration tools and custom BI backends.

**Common use cases:**
- Automated data quality checks after nightly ETL
- Parameterized SQL execution from Airflow/Dagster operators
- Query cost reporting and anomaly detection
- Building internal SQL APIs over the data lake

**When to use it:** When queries must be triggered, monitored, and results consumed programmatically rather than through the Athena Console or JDBC.

---

## AWS CLI Commands

### Verify Athena Client Access

**Purpose:** Confirm the caller can list workgroups.

**Command:**

```bash
aws athena list-work-groups --max-results 5
```

**Example Output:**

```json
{
    "WorkGroups": [
        {"Name": "primary-analytics", "State": "ENABLED"}
    ]
}
```

---

### Get Query Results Location

**Purpose:** Retrieve the S3 path of CSV results for downstream Python processing.

**Command:**

```bash
aws athena get-query-execution \
  --query-execution-id a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  --query 'QueryExecution.ResultConfiguration.OutputLocation' \
  --output text
```

**Example Output:**

```
s3://athena-query-results-prod/account-id/a1b2c3d4-e5f6-7890-abcd-ef1234567890.csv
```

---

## Advanced Commands

### Paginate Query Results

```bash
aws athena get-query-results \
  --query-execution-id a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  --max-results 1000 \
  --next-token "eyJ..."
```

### Start Query with Execution Parameters

```bash
aws athena start-query-execution \
  --query-string "SELECT COUNT(*) FROM curated.orders WHERE dt = ?" \
  --execution-parameters "2025-03-01" \
  --query-execution-context Database=curated \
  --result-configuration OutputLocation=s3://athena-query-results/account-id/ \
  --work-group primary-analytics
```

---

## Python Boto3 Examples

### Session and Paginated Results

```python
import boto3

session = boto3.Session(region_name="us-east-1")
athena = session.client("athena")

paginator = athena.get_paginator("get_query_results")
for page in paginator.paginate(QueryExecutionId="a1b2c3d4-e5f6-7890-abcd-ef1234567890"):
    for row in page["ResultSet"]["Rows"]:
        values = [col.get("VarCharValue") for col in row["Data"]]
        print(values)
```

### Data Quality Check After ETL

```python
import logging

import boto3

logger = logging.getLogger(__name__)

DQ_SQL = """
SELECT
  COUNT(*) AS total_rows,
  SUM(CASE WHEN order_id IS NULL THEN 1 ELSE 0 END) AS null_order_ids,
  SUM(CASE WHEN amount < 0 THEN 1 ELSE 0 END) AS negative_amounts
FROM curated.orders
WHERE dt = '{dt}'
"""


def validate_orders_partition(dt: str) -> dict:
    athena = boto3.client("athena")
    sql = DQ_SQL.format(dt=dt)

    qid = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": "curated"},
        ResultConfiguration={"OutputLocation": "s3://athena-query-results/account-id/"},
        WorkGroup="primary-analytics",
    )["QueryExecutionId"]

    # Poll (simplified — use waiter in production)
    import time
    while True:
        meta = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
        if meta["Status"]["State"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            break
        time.sleep(2)

    if meta["Status"]["State"] != "SUCCEEDED":
        raise RuntimeError(meta["Status"].get("StateChangeReason"))

    result = athena.get_query_results(QueryExecutionId=qid)
    row = result["ResultSet"]["Rows"][1]["Data"]
    metrics = {
        "total_rows": int(row[0]["VarCharValue"]),
        "null_order_ids": int(row[1]["VarCharValue"]),
        "negative_amounts": int(row[2]["VarCharValue"]),
    }
    logger.info("DQ metrics for dt=%s: %s", dt, metrics)
    return metrics
```

### Production-Ready — Athena Client with Waiter and S3 Result Download

```python
import csv
import io
import logging
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class AthenaConfig:
    database: str
    output_location: str
    workgroup: str
    region: str = "us-east-1"


class AthenaClient:
    def __init__(self, config: AthenaConfig):
        self.config = config
        self.athena = boto3.client("athena", region_name=config.region)
        self.s3 = boto3.client("s3", region_name=config.region)

    def execute(self, sql: str, parameters: list[str] | None = None) -> str:
        kwargs = {
            "QueryString": sql,
            "QueryExecutionContext": {"Database": self.config.database},
            "ResultConfiguration": {"OutputLocation": self.config.output_location},
            "WorkGroup": self.config.workgroup,
        }
        if parameters:
            kwargs["ExecutionParameters"] = parameters

        try:
            qid = self.athena.start_query_execution(**kwargs)["QueryExecutionId"]
        except ClientError as exc:
            logger.error("Start query failed: %s", exc.response["Error"]["Message"])
            raise

        waiter = self.athena.get_waiter("query_succeeded")
        try:
            waiter.wait(
                QueryExecutionId=qid,
                WaiterConfig={"Delay": 2, "MaxAttempts": 300},
            )
        except Exception:
            meta = self.athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
            reason = meta["Status"].get("StateChangeReason", "Query failed")
            raise RuntimeError(reason) from None

        return qid

    def fetch_rows(self, query_execution_id: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        headers: list[str] = []
        paginator = self.athena.get_paginator("get_query_results")

        for i, page in enumerate(paginator.paginate(QueryExecutionId=query_execution_id)):
            for j, row in enumerate(page["ResultSet"]["Rows"]):
                values = [col.get("VarCharValue", "") for col in row["Data"]]
                if i == 0 and j == 0:
                    headers = values
                    continue
                rows.append(dict(zip(headers, values)))
        return rows

    def download_result_csv(self, query_execution_id: str) -> str:
        meta = self.athena.get_query_execution(QueryExecutionId=query_execution_id)
        s3_path = meta["QueryExecution"]["ResultConfiguration"]["OutputLocation"]
        bucket, key = s3_path.replace("s3://", "").split("/", 1)
        obj = self.s3.get_object(Bucket=bucket, Key=key)
        return obj["Body"].read().decode("utf-8")
```

### Parameterized Query with Execution Parameters

```python
config = AthenaConfig(
    database="curated",
    output_location="s3://athena-query-results-prod/account-id/",
    workgroup="primary-analytics",
)
client = AthenaClient(config)

qid = client.execute(
    "SELECT order_id, amount FROM orders WHERE dt = ? AND status = ?",
    parameters=["2025-03-01", "SHIPPED"],
)
rows = client.fetch_rows(qid)
print(f"Returned {len(rows)} rows")
```

### Cost Anomaly Detector

```python
import boto3
from datetime import datetime, timedelta, timezone


def flag_expensive_queries(workgroup: str, threshold_mb: float = 1000) -> list[dict]:
    athena = boto3.client("athena")
    ids = athena.list_query_executions(WorkGroup=workgroup, MaxResults=50)["QueryExecutionIds"]
    executions = athena.batch_get_query_execution(QueryExecutionIds=ids)["QueryExecutions"]

    flagged = []
    for ex in executions:
        scanned = int(ex.get("Statistics", {}).get("DataScannedInBytes", 0))
        scanned_mb = scanned / 1e6
        if scanned_mb >= threshold_mb:
            flagged.append({
                "query_id": ex["QueryExecutionId"],
                "scanned_mb": round(scanned_mb, 2),
                "sql": ex["Query"][:200],
                "submitted": ex["Status"].get("SubmissionDateTime"),
            })
    return flagged
```

---

## Security Considerations

- Run Athena automation under an **IAM role** with workgroup-scoped permissions.
- Never embed **access keys** in notebooks; use SSO or instance/task roles.
- Sanitize **dynamic SQL** — prefer `ExecutionParameters` over string formatting to reduce injection risk.
- Restrict **`s3:GetObject`** on results buckets to authorized principals only.
- Log query IDs and scan bytes, not full SQL containing sensitive literals, in shared logs.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `Waiter query_succeeded` timeout | Long-running CTAS | Increase `MaxAttempts`; monitor in console |
| Empty result paginator | Query returned no rows | Check header row handling (skip row 0) |
| `InvalidRequestException` parameters | Placeholder count mismatch | Match `?` count to `ExecutionParameters` length |
| CSV download garbled | Multiline fields in data | Use `get_query_results` paginator instead of raw CSV |
| `AccessDenied` on results S3 | Role lacks read on output | Grant read on results prefix to automation role |

---

## Best Practices

- Use **`get_waiter("query_succeeded")`** instead of manual sleep loops.
- Prefer **`ExecutionParameters`** for user-supplied filter values.
- Return **query execution ID** from all wrapper functions for traceability.
- Parse results via **`get_query_results` paginator** for typed access; use S3 CSV for bulk export.
- Emit **CloudWatch metrics** on `DataScannedInBytes` from wrapper code for cost tracking.
- Centralize config (`AthenaConfig` dataclass) per environment.
- Cancel runaway queries with **`stop_query_execution`** when scan exceeds threshold mid-flight.
