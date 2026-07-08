# Athena — Queries

## Service Overview

**Amazon Athena** is a serverless interactive query service that runs standard SQL directly on data in S3 using the Glue Data Catalog (or federated connectors). You pay per data scanned; results land in a configurable S3 output location.

**Common use cases:**
- Ad-hoc analytics on curated Parquet tables in the data lake
- Data quality validation queries after ETL runs
- Exploratory analysis on raw JSON/CSV landing zones
- Federated queries joining S3 data with RDS via Athena connectors

**When to use it:** For interactive SQL without provisioning clusters. Prefer Athena over Redshift for sporadic queries on S3; use workgroups for cost controls and query isolation.

---

## AWS CLI Commands

### Start Query Execution

**Purpose:** Submit a SQL query asynchronously.

**Command:**

```bash
aws athena start-query-execution \
  --query-string "SELECT dt, COUNT(*) AS order_count, SUM(amount) AS revenue
                  FROM curated.orders
                  WHERE dt BETWEEN '2025-03-01' AND '2025-03-07'
                  GROUP BY dt
                  ORDER BY dt" \
  --query-execution-context Database=curated \
  --result-configuration OutputLocation=s3://athena-query-results/account-id/ \
  --work-group primary-analytics
```

**Example Output:**

```json
{
    "QueryExecutionId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

---

### Get Query Status

**Purpose:** Poll until a query completes or fails.

**Command:**

```bash
aws athena get-query-execution \
  --query-execution-id a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  --query 'QueryExecution.{State:Status.State,Scanned:Statistics.DataScannedInBytes,Runtime:Statistics.TotalExecutionTimeInMillis,Reason:Status.StateChangeReason}' \
  --output table
```

**Example Output:**

```
-----------------------------------------------------------------------
|                         GetQueryExecution                           |
+----------+-----------+----------------------------------------------+
| Runtime  | Scanned   |  State                                       |
+----------+-----------+----------------------------------------------+
|  4523    |  52428800 |  SUCCEEDED                                   |
+----------+-----------+----------------------------------------------+
```

**Query states:** `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`.

---

### Get Query Results

**Purpose:** Retrieve result rows (first page; paginate for large results).

**Command:**

```bash
aws athena get-query-results \
  --query-execution-id a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  --max-results 50
```

**Example Output (abbreviated):**

```json
{
    "ResultSet": {
        "Rows": [
            {"Data": [{"VarCharValue": "dt"}, {"VarCharValue": "order_count"}, {"VarCharValue": "revenue"}]},
            {"Data": [{"VarCharValue": "2025-03-01"}, {"VarCharValue": "15234"}, {"VarCharValue": "892341.50"}]},
            {"Data": [{"VarCharValue": "2025-03-02"}, {"VarCharValue": "14891"}, {"VarCharValue": "901223.00"}]}
        ]
    },
    "UpdateCount": 0
}
```

---

### Stop a Running Query

**Purpose:** Cancel an expensive or runaway query.

**Command:**

```bash
aws athena stop-query-execution \
  --query-execution-id a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

### List Recent Query Executions

**Purpose:** Audit query history for a workgroup.

**Command:**

```bash
aws athena list-query-executions \
  --work-group primary-analytics \
  --max-results 20
```

**Example Output:**

```json
{
    "QueryExecutionIds": [
        "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "b2c3d4e5-f6a7-8901-bcde-f12345678901"
    ]
}
```

---

### Run DDL — Create External Table

**Purpose:** Define a table over S3 data via Athena SQL.

**Command:**

```bash
aws athena start-query-execution \
  --query-string "
    CREATE EXTERNAL TABLE IF NOT EXISTS curated.events (
      event_id   STRING,
      user_id    BIGINT,
      event_type STRING,
      event_ts   TIMESTAMP
    )
    PARTITIONED BY (dt STRING)
    STORED AS PARQUET
    LOCATION 's3://analytics-curated/events/'
    TBLPROPERTIES ('parquet.compress'='SNAPPY')
  " \
  --query-execution-context Database=curated \
  --result-configuration OutputLocation=s3://athena-query-results/account-id/ \
  --work-group primary-analytics
```

---

### Repair Partitions (MSCK REPAIR)

**Purpose:** Register Hive-style partitions discovered on S3.

**Command:**

```bash
aws athena start-query-execution \
  --query-string "MSCK REPAIR TABLE curated.orders" \
  --query-execution-context Database=curated \
  --result-configuration OutputLocation=s3://athena-query-results/account-id/
```

---

### Batch Query with Named Query

**Purpose:** Reuse saved SQL for recurring reports.

**Command:**

```bash
# Create named query
aws athena create-named-query \
  --name daily-orders-summary \
  --database curated \
  --query-string "SELECT dt, COUNT(*) FROM orders WHERE dt = date_format(current_date - interval '1' day, '%Y-%m-%d') GROUP BY dt" \
  --work-group primary-analytics

# Execute named query
QUERY_ID=$(aws athena list-named-queries --query 'NamedQueryIds[0]' --output text)
aws athena get-named-query --named-query-id "$QUERY_ID"
```

---

## Advanced Commands

### Filter Failed Queries

```bash
aws athena list-query-executions --work-group primary-analytics --max-results 50 \
  | jq -r '.QueryExecutionIds[]' \
  | while read id; do
      aws athena get-query-execution --query-execution-id "$id" \
        --query 'QueryExecution.{Id:QueryExecutionId,State:Status.State,SQL:Query}' --output json
    done
```

### Query with Result Reuse

```bash
aws athena start-query-execution \
  --query-string "SELECT COUNT(*) FROM curated.orders WHERE dt = '2025-03-01'" \
  --query-execution-context Database=curated \
  --result-configuration OutputLocation=s3://athena-query-results/account-id/ \
  --result-reuse-configuration 'ResultReuseByAgeConfiguration={Enabled=true,MaxAgeInMinutes=60}'
```

### EXPLAIN for Performance Tuning

```bash
aws athena start-query-execution \
  --query-string "EXPLAIN SELECT * FROM curated.orders WHERE dt = '2025-03-01' AND status = 'SHIPPED'" \
  --query-execution-context Database=curated \
  --result-configuration OutputLocation=s3://athena-query-results/account-id/
```

### CTAS — Create Table As Select

```bash
aws athena start-query-execution \
  --query-string "
    CREATE TABLE curated.orders_daily_summary
    WITH (
      format = 'PARQUET',
      parquet_compression = 'SNAPPY',
      external_location = 's3://analytics-curated/summaries/orders_daily/',
      partitioned_by = ARRAY['dt']
    ) AS
    SELECT dt, COUNT(*) AS cnt, SUM(amount) AS revenue
    FROM curated.orders
    WHERE dt >= '2025-01-01'
    GROUP BY dt
  " \
  --query-execution-context Database=curated \
  --result-configuration OutputLocation=s3://athena-query-results/account-id/
```

---

## Python Boto3 Examples

### Basic — Run Query and Fetch Results

```python
import time

import boto3

athena = boto3.client("athena")

response = athena.start_query_execution(
    QueryString="SELECT COUNT(*) FROM curated.orders WHERE dt = '2025-03-01'",
    QueryExecutionContext={"Database": "curated"},
    ResultConfiguration={"OutputLocation": "s3://athena-query-results/account-id/"},
    WorkGroup="primary-analytics",
)
query_id = response["QueryExecutionId"]

while True:
    status = athena.get_query_execution(QueryExecutionId=query_id)
    state = status["QueryExecution"]["Status"]["State"]
    if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
        break
    time.sleep(2)

results = athena.get_query_results(QueryExecutionId=query_id)
for row in results["ResultSet"]["Rows"]:
    print([col.get("VarCharValue") for col in row["Data"]])
```

### Production-Ready — Query Runner with Cost Logging

```python
import logging
import time
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    query_id: str
    state: str
    data_scanned_bytes: int
    execution_time_ms: int
    rows: list[list[str]]


def run_athena_query(
    sql: str,
    database: str,
    output_location: str,
    workgroup: str = "primary-analytics",
    poll_seconds: float = 2.0,
) -> QueryResult:
    athena = boto3.client("athena")

    try:
        qid = athena.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={"Database": database},
            ResultConfiguration={"OutputLocation": output_location},
            WorkGroup=workgroup,
        )["QueryExecutionId"]
    except ClientError as exc:
        logger.error("Failed to start query: %s", exc.response["Error"]["Message"])
        raise

    while True:
        exec_meta = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
        state = exec_meta["Status"]["State"]
        if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            break
        time.sleep(poll_seconds)

    stats = exec_meta.get("Statistics", {})
    scanned = int(stats.get("DataScannedInBytes", 0))
    runtime = int(stats.get("TotalExecutionTimeInMillis", 0))
    logger.info("Query %s: state=%s scanned=%.2f MB runtime=%d ms", qid, state, scanned / 1e6, runtime)

    rows: list[list[str]] = []
    if state == "SUCCEEDED":
        paginator = athena.get_paginator("get_query_results")
        for page in paginator.paginate(QueryExecutionId=qid):
            for row in page["ResultSet"]["Rows"]:
                rows.append([col.get("VarCharValue", "") for col in row["Data"]])

    if state == "FAILED":
        reason = exec_meta["Status"].get("StateChangeReason", "Unknown")
        raise RuntimeError(f"Athena query failed: {reason}")

    return QueryResult(qid, state, scanned, runtime, rows)
```

---

## Security Considerations

- Enforce **workgroup** settings: output location, encryption, and **bytes scanned cutoff**.
- Encrypt query results with **SSE-S3** or **SSE-KMS** via workgroup `ResultConfiguration`.
- Grant **`athena:StartQueryExecution`** only on approved workgroups; scope **`s3:GetObject`** to data prefixes.
- Use **Lake Formation** for column/row-level access on sensitive tables.
- Avoid embedding credentials in SQL; use **Athena federated connectors** with Secrets Manager.

---

## Troubleshooting

| Error / Symptom | Root Cause | Resolution |
|-----------------|------------|------------|
| `AccessDenied` on S3 output | Missing write on results bucket | Grant `s3:PutObject` on output prefix to caller/workgroup role |
| `TABLE_NOT_FOUND` | Wrong database or stale catalog | Verify `database.table`; run crawler or MSCK REPAIR |
| Query scans entire bucket | Missing partition filter | Always filter on partition columns (`WHERE dt = ...`) |
| `HIVE_PARTITION_SCHEMA_MISMATCH` | Inconsistent partition schema | Align partition folder structure with table definition |
| `Query exhausted resources` | Too much data scanned | Add partitions, use Parquet, enable query result reuse |
| Slow queries | Small files, no column pruning | Compact files; select only needed columns; use CTAS |
| `Insufficient permissions` on KMS | Workgroup uses CMK | Grant `kms:Decrypt/GenerateDataKey` on the key |

---

## Best Practices

- Store data as **partitioned Parquet** with Snappy compression — reduces scan cost 10–100x vs CSV.
- Always filter on **partition columns** first in the `WHERE` clause.
- Use **workgroups** per team/environment with per-query and per-workgroup scan limits.
- Save recurring SQL as **named queries** or manage in Git with CI/CD.
- Use **CTAS/INSERT INTO** for materialized summaries instead of re-scanning raw tables daily.
- Enable **Athena query result reuse** for dashboard-style repeated queries.
- Monitor **`DataScannedInBytes`** in CloudWatch; alert on anomalies.
- Set lifecycle rules on the **query results bucket** to expire objects after 7–30 days.
