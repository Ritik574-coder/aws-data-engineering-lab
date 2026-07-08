# Redshift — Data Warehouse Operations

## Service Overview

This guide covers **SQL and CLI operations** for loading, transforming, and querying data in Amazon Redshift — the core workflows for analytics engineers and data platform teams.

**Common patterns:**
- **COPY** from S3 (Parquet, CSV, JSON) into staging tables
- **UNLOAD** query results back to S3 for downstream systems
- **Spectrum** external tables over data lake zones
- **Incremental loads** via staging + MERGE (DELETE/INSERT)
- **Materialized views** for BI performance

**Architecture flow:**

```
S3 (raw/curated) → COPY → staging → transform SQL → fact/dim tables → BI tools
                              ↓
                    Spectrum (external schema) ← Glue Data Catalog
```

---

## AWS CLI Commands

Redshift SQL runs via `psql`, **Redshift Data API**, or the Query Editor v2. CLI commands below manage infrastructure and execute SQL programmatically.

### Execute SQL via Redshift Data API

**Purpose:** Run DDL/DML without persistent JDBC connection (Lambda, Step Functions).

**Command:**

```bash
aws redshift-data execute-statement \
  --cluster-identifier analytics-dw \
  --database analytics \
  --db-user etl_service \
  --sql "COPY staging.orders FROM 's3://my-data-lake-raw/orders/dt=2025-03-01/' IAM_ROLE 'arn:aws:iam::123456789012:role/RedshiftLoadRole' FORMAT AS PARQUET;"
```

**Example Output:**

```json
{
    "Id": "01234567-89ab-cdef-0123-456789abcdef",
    "CreatedAt": "2025-03-01T06:00:00+00:00"
}
```

---

### Check Statement Status

**Command:**

```bash
aws redshift-data describe-statement \
  --id 01234567-89ab-cdef-0123-456789abcdef \
  --query '{Status:Status,Duration:Duration,Error:Error}' \
  --output table
```

---

### Fetch Query Results

**Command:**

```bash
aws redshift-data get-statement-result \
  --id 01234567-89ab-cdef-0123-456789abcdef \
  --output table
```

---

### List Recent Statements

**Command:**

```bash
aws redshift-data list-statements \
  --status ALL \
  --max-results 20 \
  --query 'Statements[].{Id:Id,Status:Status,QueryString:QueryString,Duration:Duration}' \
  --output table
```

---

### Serverless — Execute Statement

**Command:**

```bash
aws redshift-data execute-statement \
  --workgroup-name analytics-serverless \
  --database analytics \
  --secret-arn arn:aws:secretsmanager:us-east-1:123456789012:secret:redshift/analytics-admin \
  --sql "SELECT COUNT(*) FROM public.orders_fact WHERE order_date = '2025-03-01';"
```

---

### Describe Tables (Data API)

**Command:**

```bash
aws redshift-data list-tables \
  --cluster-identifier analytics-dw \
  --database analytics \
  --db-user etl_service \
  --schema-pattern public \
  --query 'Tables[].{Name:name,Type:type}' \
  --output table
```

---

## SQL Operations (via psql or Data API)

### COPY from S3 — Parquet (Recommended)

**Purpose:** Bulk load columnar data from the data lake.

```sql
COPY staging.orders
FROM 's3://my-data-lake-curated/orders/year=2025/month=03/'
IAM_ROLE 'arn:aws:iam::123456789012:role/RedshiftLoadRole'
FORMAT AS PARQUET;
```

**With manifest and compression:**

```sql
COPY staging.events
FROM 's3://my-data-lake-raw/events/manifest.json'
IAM_ROLE 'arn:aws:iam::123456789012:role/RedshiftLoadRole'
MANIFEST
GZIP
ACCEPTINVCHARS
TRUNCATECOLUMNS
COMPUPDATE OFF
STATUPDATE OFF;
```

---

### UNLOAD to S3

**Purpose:** Export query results for Athena, ML pipelines, or archival.

```sql
UNLOAD ('SELECT * FROM analytics.orders_fact WHERE order_date >= ''2025-01-01''')
TO 's3://analytics-exports/orders/year=2025/'
IAM_ROLE 'arn:aws:iam::123456789012:role/RedshiftUnloadRole'
FORMAT AS PARQUET
PARALLEL ON
ALLOWOVERWRITE
MAXFILESIZE 256 MB;
```

---

### Incremental Load Pattern

```sql
BEGIN;

DELETE FROM public.orders_fact
USING staging.orders s
WHERE orders_fact.order_id = s.order_id
  AND s.order_date = '2025-03-01';

INSERT INTO public.orders_fact
SELECT order_id, customer_id, order_date, amount, updated_at
FROM staging.orders
WHERE order_date = '2025-03-01';

TRUNCATE staging.orders;

COMMIT;
```

---

### Spectrum External Table

**Purpose:** Query S3 data lake without loading into Redshift storage.

```sql
CREATE EXTERNAL SCHEMA spectrum_lake
FROM DATA CATALOG
DATABASE 'analytics_glue_db'
IAM_ROLE 'arn:aws:iam::123456789012:role/RedshiftSpectrumRole'
CREATE EXTERNAL DATABASE IF NOT EXISTS;

SELECT o.order_id, c.customer_name
FROM spectrum_lake.orders_parquet o
JOIN public.dim_customers c ON o.customer_id = c.customer_id
WHERE o.year = '2025' AND o.month = '03';
```

---

### Distribution and Sort Keys

```sql
CREATE TABLE public.orders_fact (
    order_id       BIGINT,
    customer_id    INT,
    order_date     DATE,
    amount         DECIMAL(18,2),
    updated_at     TIMESTAMP
)
DISTKEY (customer_id)
SORTKEY (order_date, order_id);
```

---

### Vacuum and Analyze

```sql
VACUUM public.orders_fact;
ANALYZE public.orders_fact;
```

---

## Advanced Commands

### Batch SQL via Data API with Secrets Manager

```bash
SECRET_ARN="arn:aws:secretsmanager:us-east-1:123456789012:secret:redshift/etl"

STATEMENT_ID=$(aws redshift-data execute-statement \
  --cluster-identifier analytics-dw \
  --database analytics \
  --secret-arn "$SECRET_ARN" \
  --sql "BEGIN; TRUNCATE staging.orders; COPY staging.orders FROM 's3://my-data-lake-curated/orders/dt=2025-03-01/' IAM_ROLE 'arn:aws:iam::123456789012:role/RedshiftLoadRole' FORMAT AS PARQUET; COMMIT;" \
  --query 'Id' --output text)

aws redshift-data wait statement-finished --id "$STATEMENT_ID"
aws redshift-data describe-statement --id "$STATEMENT_ID"
```

### Cancel Long-Running Query

```bash
aws redshift-data cancel-statement --id 01234567-89ab-cdef-0123-456789abcdef
```

### Execute Statement with Result Streaming

```bash
aws redshift-data execute-statement \
  --cluster-identifier analytics-dw \
  --database analytics \
  --db-user etl_service \
  --sql "SELECT * FROM stl_load_errors ORDER BY starttime DESC LIMIT 10;" \
  --result-format JSON
```

### Query Monitoring via System Tables

```sql
-- Recent load errors
SELECT query, filename, line_number, colname, err_reason
FROM stl_load_errors
ORDER BY starttime DESC
LIMIT 20;

-- Table skew
SELECT "table", skew_rows, skew_sortkey1
FROM svv_table_info
WHERE "table" = 'orders_fact';
```

---

## Python (Boto3) Examples

### Execute COPY via Data API

```python
import boto3

client = boto3.client("redshift-data")

resp = client.execute_statement(
    ClusterIdentifier="analytics-dw",
    Database="analytics",
    DbUser="etl_service",
    Sql="""
        COPY staging.orders
        FROM 's3://my-data-lake-curated/orders/dt=2025-03-01/'
        IAM_ROLE 'arn:aws:iam::123456789012:role/RedshiftLoadRole'
        FORMAT AS PARQUET;
    """,
)
print(resp["Id"])
```

See [redshift_python_examples.md](redshift_python_examples.md) for full async polling and result parsing.

---

## Security Considerations

- Use **IAM roles** for COPY/UNLOAD — grant `s3:GetObject`/`s3:PutObject` on specific prefixes only.
- Store database credentials in **Secrets Manager**; reference via Data API `--secret-arn`.
- Restrict **`etl_service`** user to staging schemas; use **`BI_readonly`** role for analysts.
- Enable **SSL** for all client connections (`require` in JDBC URL).
- Audit **`stl_userlog`** and S3 audit logs for sensitive table access.
- Mask PII in marts using **Dynamic Data Masking** (where available) or ETL transforms.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `Spectrum Scan Error: Access Denied` | Spectrum role lacks S3/Glue permissions | Attach S3 read + `glue:Get*` to Spectrum IAM role |
| `Load into table failed` (stl_load_errors) | Schema mismatch, bad dates, encoding | Query `stl_load_errors`; fix column order/types |
| `Disk full` | Too much data on older node types | Vacuum; resize; use RA3; archive old partitions |
| Slow COPY | Too many small files | Compact S3 to 128–256 MB files before COPY |
| `Serializable isolation violation` | Concurrent DELETE/INSERT on same keys | Serialize incremental loads; use table locks |
| External schema not found | Glue DB name mismatch | Verify `CREATE EXTERNAL SCHEMA` database name |

---

## Best Practices

- Load into **staging tables** (`STAGING` schema) then transform — never COPY directly into fact tables in prod.
- Use **Parquet** with Snappy compression for COPY — faster and cheaper than CSV.
- Set **`COMPUPDATE OFF STATUPDATE OFF`** during bulk loads; run `ANALYZE` after.
- Design **DISTKEY** on high-cardinality join columns; **SORTKEY** on filter columns (dates).
- Use **Spectrum** for cold/historical data; load hot partitions into native tables.
- Schedule **VACUUM** during off-peak; monitor `svv_table_info` for unsorted and skew percentages.
- Implement **idempotent daily loads** with DELETE + INSERT keyed on business date.
- Use **materialized views** with auto-refresh for heavy BI aggregations.
- Monitor **WLM queues** — separate ETL and reporting workloads into different queues.
- **UNLOAD** large exports instead of SELECT into client tools to avoid memory pressure.
