# Glue — Data Catalog

## Service Overview

The **AWS Glue Data Catalog** is a centralized metadata repository (Hive-compatible) that stores databases, tables, partitions, and connections. It is the metadata layer shared by **Athena**, **Redshift Spectrum**, **EMR**, and **Glue ETL jobs**.

**Common use cases:**
- Register curated Parquet tables for Athena SQL queries
- Manage database namespaces (`raw_lake`, `curated`, `sandbox`)
- Define partition keys for time-series analytics
- Store JDBC connection metadata for federated queries

**When to use it:** Whenever SQL engines or Spark jobs need table definitions over S3 data. The catalog is the single source of truth for schema and partition metadata in modern data lakes.

---

## AWS CLI Commands

### List Databases

**Purpose:** List all databases in the Glue Data Catalog.

**Command:**

```bash
aws glue get-databases --max-results 50
```

**Example Output (abbreviated):**

```json
{
    "DatabaseList": [
        {
            "Name": "raw_lake",
            "Description": "Raw landing zone tables",
            "LocationUri": "s3://my-data-lake-raw/"
        },
        {
            "Name": "curated",
            "Description": "Cleaned and modeled datasets",
            "LocationUri": "s3://analytics-curated/"
        }
    ]
}
```

---

### Create a Database

**Purpose:** Define a logical namespace for related tables.

**Command:**

```bash
aws glue create-database \
  --database-input '{
    "Name": "curated",
    "Description": "Production curated datasets",
    "LocationUri": "s3://analytics-curated/",
    "Parameters": {"owner": "data-platform"}
  }'
```

**Example Output:** *(empty on success — HTTP 200)*

---

### List Tables in a Database

**Purpose:** Enumerate tables available for Athena queries.

**Command:**

```bash
aws glue get-tables --database-name curated --max-results 100
```

**Example Output (abbreviated):**

```json
{
    "TableList": [
        {
            "Name": "orders",
            "DatabaseName": "curated",
            "StorageDescriptor": {
                "Location": "s3://analytics-curated/orders/",
                "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
                "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
                "SerdeInfo": {
                    "SerializationLibrary": "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
                },
                "Columns": [
                    {"Name": "order_id", "Type": "bigint"},
                    {"Name": "customer_id", "Type": "bigint"},
                    {"Name": "amount", "Type": "decimal(10,2)"}
                ]
            },
            "PartitionKeys": [{"Name": "dt", "Type": "string"}]
        }
    ]
}
```

---

### Get Table Definition

**Purpose:** Inspect full schema, location, and partition keys.

**Command:**

```bash
aws glue get-table --database-name curated --name orders
```

---

### Create a Table (Parquet, Partitioned)

**Purpose:** Explicitly register a table for Athena (without a crawler).

**Command:**

```bash
aws glue create-table \
  --database-name curated \
  --table-input '{
    "Name": "orders",
    "Description": "Daily order facts",
    "TableType": "EXTERNAL_TABLE",
    "Parameters": {
      "classification": "parquet",
      "projection.enabled": "true",
      "projection.dt.type": "date",
      "projection.dt.range": "2024-01-01,NOW",
      "projection.dt.format": "yyyy-MM-dd",
      "storage.location.template": "s3://analytics-curated/orders/dt=${dt}/"
    },
    "PartitionKeys": [{"Name": "dt", "Type": "string"}],
    "StorageDescriptor": {
      "Columns": [
        {"Name": "order_id", "Type": "bigint"},
        {"Name": "customer_id", "Type": "bigint"},
        {"Name": "amount", "Type": "decimal(10,2)"},
        {"Name": "status", "Type": "string"}
      ],
      "Location": "s3://analytics-curated/orders/",
      "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
      "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
      "SerdeInfo": {
        "SerializationLibrary": "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
      }
    }
  }'
```

---

### List Partitions

**Purpose:** View registered partitions for a table (used by Athena partition pruning).

**Command:**

```bash
aws glue get-partitions \
  --database-name curated \
  --table-name orders \
  --max-results 50
```

**Example Output (abbreviated):**

```json
{
    "Partitions": [
        {
            "Values": ["2025-03-01"],
            "StorageDescriptor": {
                "Location": "s3://analytics-curated/orders/dt=2025-03-01/"
            },
            "CreationTime": "2025-03-01T07:00:00.000+00:00"
        }
    ]
}
```

---

### Add Partition Manually

**Purpose:** Register a new partition after ETL writes data (alternative to crawler).

**Command:**

```bash
aws glue create-partition \
  --database-name curated \
  --table-name orders \
  --partition-input '{
    "Values": ["2025-03-01"],
    "StorageDescriptor": {
      "Location": "s3://analytics-curated/orders/dt=2025-03-01/",
      "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
      "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
      "SerdeInfo": {
        "SerializationLibrary": "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
      }
    }
  }'
```

---

### Batch Create Partitions

**Purpose:** Register multiple partitions in one API call (backfill scenario).

**Command:**

```bash
aws glue batch-create-partition \
  --database-name curated \
  --table-name orders \
  --partition-input-list '[
    {"Values": ["2025-03-01"], "StorageDescriptor": {"Location": "s3://analytics-curated/orders/dt=2025-03-01/"}},
    {"Values": ["2025-03-02"], "StorageDescriptor": {"Location": "s3://analytics-curated/orders/dt=2025-03-02/"}}
  ]'
```

---

### Delete a Table

**Purpose:** Remove catalog metadata (does not delete S3 data).

**Command:**

```bash
aws glue delete-table --database-name curated --name orders
```

---

## Advanced Commands

### Search Tables Across Databases

```bash
aws glue search-tables \
  --search-text "orders" \
  --filters '[
    {"Key": "DatabaseName", "Value": "curated"},
    {"Key": "TableType", "Value": "EXTERNAL_TABLE"}
  ]'
```

### Update Table Schema (Add Column)

```bash
aws glue update-table \
  --database-name curated \
  --table-input '{
    "Name": "orders",
    "StorageDescriptor": {
      "Columns": [
        {"Name": "order_id", "Type": "bigint"},
        {"Name": "customer_id", "Type": "bigint"},
        {"Name": "amount", "Type": "decimal(10,2)"},
        {"Name": "status", "Type": "string"},
        {"Name": "currency", "Type": "string"}
      ],
      "Location": "s3://analytics-curated/orders/",
      "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
      "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
      "SerdeInfo": {"SerializationLibrary": "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"}
    }
  }'
```

### Get Connection (JDBC)

```bash
aws glue get-connection --name prod-rds-postgres
```

### Paginate Partitions

```bash
aws glue get-partitions \
  --database-name curated \
  --table-name orders \
  --segment '{"SegmentNumber": 0, "TotalSegments": 4}' \
  --max-results 100
```

---

## Python Boto3 Examples

### Basic — List Tables

```python
import boto3

glue = boto3.client("glue")

paginator = glue.get_paginator("get_tables")
for page in paginator.paginate(DatabaseName="curated"):
    for table in page["TableList"]:
        print(table["Name"], table["StorageDescriptor"]["Location"])
```

### Production-Ready — Register Partition After ETL

```python
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def add_daily_partition(
    database: str,
    table: str,
    partition_date: str,
    s3_base: str,
) -> None:
    glue = boto3.client("glue")
    location = f"{s3_base.rstrip('/')}/dt={partition_date}/"

    partition_input = {
        "Values": [partition_date],
        "StorageDescriptor": {
            "Location": location,
            "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
            "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
            "SerdeInfo": {
                "SerializationLibrary": "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
            },
        },
    }

    try:
        glue.create_partition(
            DatabaseName=database,
            TableName=table,
            PartitionInput=partition_input,
        )
        logger.info("Created partition dt=%s on %s.%s", partition_date, database, table)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "AlreadyExistsException":
            logger.info("Partition dt=%s already exists", partition_date)
            return
        raise
```

---

## Security Considerations

- Use **Lake Formation** to grant fine-grained table/column/row permissions beyond IAM.
- Restrict **`glue:CreateTable`**, **`glue:DeleteTable`**, and **`glue:UpdateTable`** to CI/CD roles and data platform teams.
- Tag databases and tables for **data classification** (`PII`, `Confidential`, `Public`).
- JDBC connections store credentials in **Secrets Manager** — enforce rotation and least-privilege DB users.
- Enable **CloudTrail** data events for catalog mutations in regulated environments.

---

## Troubleshooting

| Error / Symptom | Root Cause | Resolution |
|-----------------|------------|------------|
| Athena `TABLE_NOT_FOUND` | Table in wrong database or region | Verify `database.table` and workgroup region |
| `AlreadyExistsException` | Duplicate partition registration | Use idempotent create or `batch-create-partition` with error handling |
| Queries scan all data | Partitions not registered | Run crawler, `MSCK REPAIR TABLE`, or `create-partition` |
| Schema mismatch | Parquet evolved but catalog stale | Update table columns or re-crawl |
| `AccessDenied` in Athena | Lake Formation or IAM gap | Check LF grants and S3 prefix permissions |
| Empty query results | Wrong `Location` in partition | Confirm S3 path matches partition values |

---

## Best Practices

- Organize databases by **zone** (`raw`, `curated`, `mart`) and **environment** (`dev`, `prod`).
- Prefer **partition projection** for high-cardinality date partitions to avoid millions of catalog entries.
- Register partitions **in the ETL job** (via API) for deterministic metadata — use crawlers as a safety net.
- Version table schemas; document breaking changes in a **schema registry** or Git repo.
- Use **EXTERNAL_TABLE** type always — never managed tables on S3 for data lakes.
- Apply **table properties** (`classification`, `compressionType`) for optimizer hints.
- Clean up stale partitions periodically to keep catalog queries fast.
- Manage catalog objects with **IaC** (Terraform `aws_glue_catalog_table`) for reproducibility.
