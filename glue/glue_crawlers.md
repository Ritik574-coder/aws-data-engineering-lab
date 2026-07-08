# Glue — Crawlers

## Service Overview

**AWS Glue Crawlers** automatically scan data sources (S3, JDBC, DynamoDB, MongoDB, etc.), infer schemas, and register or update tables in the **Glue Data Catalog**. They are the primary mechanism for keeping catalog metadata in sync with evolving data lake files.

**Common use cases:**
- Auto-discover new partitions in S3 (`year=/month=/day=`)
- Register JDBC tables from operational databases for Athena federated queries
- Detect schema changes (new columns) after upstream schema drift
- Bootstrap catalog tables before the first Athena or Redshift Spectrum query

**When to use it:** When metadata must stay synchronized with file-based or JDBC sources without manual DDL maintenance. Prefer crawlers for discovery; use explicit Glue jobs for complex schema logic.

---

## AWS CLI Commands

### List Crawlers

**Purpose:** List all crawler definitions in the account.

**Command:**

```bash
aws glue list-crawlers --max-results 50
```

**Example Output:**

```json
{
    "CrawlerNames": [
        "raw-orders-s3-crawler",
        "rds-customers-jdbc-crawler",
        "events-json-crawler"
    ]
}
```

---

### Get Crawler Configuration

**Purpose:** Inspect targets, schedule, and IAM role for a crawler.

**Command:**

```bash
aws glue get-crawler --name raw-orders-s3-crawler
```

**Example Output (abbreviated):**

```json
{
    "Crawler": {
        "Name": "raw-orders-s3-crawler",
        "Role": "arn:aws:iam::123456789012:role/GlueCrawlerRole",
        "DatabaseName": "raw_lake",
        "Targets": {
            "S3Targets": [
                {
                    "Path": "s3://my-data-lake-raw/orders/",
                    "Exclusions": ["**/_temporary/**", "**/.spark/**"]
                }
            ]
        },
        "SchemaChangePolicy": {
            "UpdateBehavior": "UPDATE_IN_DATABASE",
            "DeleteBehavior": "LOG"
        },
        "RecrawlPolicy": {
            "RecrawlBehavior": "CRAWL_NEW_FOLDERS_ONLY"
        },
        "Schedule": "cron(0 6 * * ? *)"
    }
}
```

---

### Start a Crawler

**Purpose:** Trigger an on-demand crawl (after new data lands or schema changes).

**Command:**

```bash
aws glue start-crawler --name raw-orders-s3-crawler
```

**Example Output:** *(empty on success — HTTP 200)*

**Explanation:** Only one crawl can run per crawler at a time. Check status with `get-crawler`.

---

### Get Crawler Status

**Purpose:** Determine if a crawl is running, succeeded, or failed.

**Command:**

```bash
aws glue get-crawler --name raw-orders-s3-crawler \
  --query 'Crawler.{State:State,LastCrawl:LastCrawl}' \
  --output table
```

**Example Output:**

```
------------------------------------------------------------------
|                          GetCrawler                            |
+-----------+----------------------------------------------------+
|  State    |  READY                                             |
+-----------+----------------------------------------------------+
||                          LastCrawl                           ||
|+-------------------+------------------------------------------+|
||  Status           |  SUCCEEDED                               ||
||  StartTime        |  2025-03-01T06:05:00+00:00               ||
||  Message          |  Tables updated: 1, Partitions added: 3  ||
|+-------------------+------------------------------------------+|
```

**Crawler states:** `READY`, `RUNNING`, `STOPPING`.

---

### Stop a Crawler

**Purpose:** Cancel a long-running crawl.

**Command:**

```bash
aws glue stop-crawler --name raw-orders-s3-crawler
```

---

### Create an S3 Crawler

**Purpose:** Register a new crawler for a data lake prefix.

**Command:**

```bash
aws glue create-crawler \
  --name raw-orders-s3-crawler \
  --role GlueCrawlerRole \
  --database-name raw_lake \
  --targets '{
    "S3Targets": [{
      "Path": "s3://my-data-lake-raw/orders/",
      "Exclusions": ["**/_temporary/**", "**/_SUCCESS"]
    }]
  }' \
  --schema-change-policy '{
    "UpdateBehavior": "UPDATE_IN_DATABASE",
    "DeleteBehavior": "LOG"
  }' \
  --recrawl-policy '{"RecrawlBehavior": "CRAWL_NEW_FOLDERS_ONLY"}' \
  --schedule "cron(0 6 * * ? *)"
```

**Example Output:**

```json
{
    "Name": "raw-orders-s3-crawler"
}
```

---

### Create a JDBC Crawler

**Purpose:** Discover tables from an RDS or other JDBC source via a Glue connection.

**Command:**

```bash
aws glue create-crawler \
  --name rds-customers-jdbc-crawler \
  --role GlueCrawlerRole \
  --database-name operational_db \
  --targets '{
    "JdbcTargets": [{
      "ConnectionName": "prod-rds-postgres",
      "Path": "analytics_db/%",
      "Exclusions": ["pg_catalog%", "information_schema%"]
    }]
  }'
```

---

### Update Crawler Schedule

**Purpose:** Change when a crawler runs (e.g., after daily ETL completes).

**Command:**

```bash
aws glue update-crawler \
  --name raw-orders-s3-crawler \
  --schedule "cron(30 7 * * ? *)"
```

---

### Delete a Crawler

**Purpose:** Remove crawler definition (does not delete catalog tables).

**Command:**

```bash
aws glue delete-crawler --name raw-orders-s3-crawler
```

---

## Advanced Commands

### List Crawler Metrics (Recent Runs)

```bash
aws glue get-crawler-metrics \
  --crawler-name-list raw-orders-s3-crawler events-json-crawler \
  --query 'CrawlerMetricsList[].{Name:CrawlerName,State:State,LastRun:LastRuntimeSeconds,Tables:TablesCreated}' \
  --output table
```

### Crawl Specific Tables Only (JDBC)

```bash
aws glue update-crawler \
  --name rds-customers-jdbc-crawler \
  --targets '{
    "JdbcTargets": [{
      "ConnectionName": "prod-rds-postgres",
      "Path": "analytics_db/customers"
    }]
  }'
```

### Filter Crawlers by Tag

```bash
aws glue get-tags \
  --resource-arn arn:aws:glue:us-east-1:123456789012:crawler/raw-orders-s3-crawler
```

### Batch Get Crawlers

```bash
aws glue batch-get-crawlers \
  --crawler-names raw-orders-s3-crawler events-json-crawler \
  --query 'Crawlers[].{Name:Name,Database:DatabaseName,State:State}' \
  --output table
```

---

## Python Boto3 Examples

### Basic — Start Crawler and Wait

```python
import time

import boto3

glue = boto3.client("glue")
crawler_name = "raw-orders-s3-crawler"

glue.start_crawler(Name=crawler_name)

while True:
    state = glue.get_crawler(Name=crawler_name)["Crawler"]["State"]
    print(f"Crawler state: {state}")
    if state == "READY":
        last = glue.get_crawler(Name=crawler_name)["Crawler"]["LastCrawl"]
        print(f"Last crawl: {last['Status']} — {last.get('Message', '')}")
        break
    time.sleep(15)
```

### Production-Ready — Conditional Crawl After ETL

```python
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def run_crawler_if_ready(crawler_name: str) -> None:
    glue = boto3.client("glue")

    try:
        crawler = glue.get_crawler(Name=crawler_name)["Crawler"]
        if crawler["State"] == "RUNNING":
            logger.info("Crawler %s already running; skipping start", crawler_name)
            return

        glue.start_crawler(Name=crawler_name)
        logger.info("Started crawler %s", crawler_name)

    except ClientError as exc:
        if exc.response["Error"]["Code"] == "CrawlerRunningException":
            logger.warning("Crawler %s is already running", crawler_name)
            return
        raise
```

---

## Security Considerations

- Crawler IAM role needs **`s3:ListBucket`/`GetObject`** on source prefixes and **`glue:*`** catalog permissions scoped to target databases.
- JDBC crawlers require **Secrets Manager** or connection credentials — restrict `glue:GetConnection` to authorized roles.
- Use **Lake Formation** permissions to govern who can read tables discovered by crawlers.
- Exclude sensitive paths (`**/pii/**`) via **S3 target exclusions** if those datasets should not be cataloged.
- Enable **CloudTrail** for `StartCrawler` and `UpdateCrawler` API calls in production accounts.

---

## Troubleshooting

| Error / Symptom | Root Cause | Resolution |
|-----------------|------------|------------|
| `CrawlerRunningException` | Concurrent start attempt | Wait for current crawl to finish or stop it |
| Tables not updating | `RecrawlBehavior` set to `CRAWL_EVERYTHING` disabled new folders | Use `CRAWL_NEW_FOLDERS_ONLY` for partitioned lakes |
| Duplicate tables created | Inconsistent folder structure | Standardize partition layout; use one table per dataset prefix |
| Schema columns all `string` | JSON/CSV without type hints | Add Glue classifier or convert to Parquet with explicit schema |
| JDBC crawl fails | VPC/security group issue | Verify Glue connection subnet and RDS inbound rules |
| Partitions missing | `_SUCCESS` or `_temporary` confusing crawler | Add exclusions; run MSCK REPAIR in Athena if using Hive-style partitions |
| `AccessDenied` on S3 | Crawler role missing permissions | Grant List/Get on bucket ARN and prefix |

---

## Best Practices

- Run crawlers **after** ETL completes (EventBridge rule or Step Functions step), not on every small file upload.
- Use **`CRAWL_NEW_FOLDERS_ONLY`** for large partitioned lakes to reduce cost and runtime.
- Set **`DeleteBehavior: LOG`** (not `DELETE_FROM_DATABASE`) to avoid accidental table drops when S3 data is temporarily missing.
- Apply **consistent partition naming** (`dt=YYYY-MM-DD`) so crawlers and Athena agree on partition keys.
- For stable schemas, consider **defining tables explicitly** (CloudFormation/Glue API) and use crawlers only for partition discovery.
- Exclude temp paths: `**/_temporary/**`, `**/.spark/**`, `**/_SUCCESS`.
- Monitor **crawler DPU-hours** in Cost Explorer; schedule off-peak for large buckets.
- Tag crawlers with `Environment`, `DataDomain`, and `SourceSystem` for operational clarity.
