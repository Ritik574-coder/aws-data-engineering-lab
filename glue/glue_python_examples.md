# Glue — Python Boto3 Examples

## Service Overview

Boto3 provides the `glue` client for programmatic access to Glue Jobs, Crawlers, Workflows, Triggers, and the Data Catalog. Data engineers use it for pipeline orchestration, operational tooling, and metadata automation outside the AWS Console.

**Common use cases:**
- Trigger Glue jobs from Lambda or Step Functions with custom arguments
- Automate partition registration after Spark ETL completes
- Build internal data platform APIs for catalog discovery
- Monitor job runs and emit metrics to CloudWatch or Datadog

**When to use it:** When CLI commands are insufficient — e.g., dynamic job triggering, retry logic, integration with Python orchestration frameworks (Airflow, Dagster, Prefect).

---

## AWS CLI Commands

### Verify Glue API Access

**Purpose:** Confirm credentials can call Glue APIs.

**Command:**

```bash
aws glue get-databases --max-results 1
```

**Example Output:**

```json
{
    "DatabaseList": [
        {"Name": "curated", "CreateTime": "2025-01-15T10:00:00.000+00:00"}
    ]
}
```

---

### Get Job Run for Script Integration

**Purpose:** Retrieve run metadata to pass into Python polling loops.

**Command:**

```bash
aws glue get-job-runs \
  --job-name orders-daily-etl \
  --max-results 1 \
  --query 'JobRuns[0].{Id:Id,State:JobRunState,Duration:ExecutionTime}' \
  --output json
```

**Example Output:**

```json
{
    "Id": "jr_a1b2c3d4e5f6789012345678",
    "State": "SUCCEEDED",
    "Duration": 861
}
```

---

### Export Catalog Table as JSON

**Purpose:** Serialize table definition for backup or cross-account replication.

**Command:**

```bash
aws glue get-table \
  --database-name curated \
  --name orders \
  --query 'Table.{Name:Name,Columns:StorageDescriptor.Columns,Partitions:PartitionKeys,Location:StorageDescriptor.Location}' \
  --output json > orders_table_schema.json
```

---

## Advanced Commands

### Paginate All Job Runs with Query

```bash
aws glue get-job-runs \
  --job-name orders-daily-etl \
  --starting-token "eyJ..." \
  --max-results 100
```

### Batch Stop Multiple Runs

```bash
aws glue batch-stop-job-run \
  --job-name orders-daily-etl \
  --job-run-ids jr_abc123 jr_def456
```

### List Workflows and Triggers

```bash
aws glue list-workflows
aws glue get-triggers --query 'Triggers[?Type==`SCHEDULED`].Name' --output text
```

---

## Python Boto3 Examples

### Session and Client Setup

```python
import boto3
from botocore.config import Config

config = Config(retries={"max_attempts": 10, "mode": "adaptive"})
session = boto3.Session(profile_name="data-engineer", region_name="us-east-1")
glue = session.client("glue", config=config)
```

### Orchestrate Job → Crawler Pipeline

```python
import logging
import time

import boto3

logger = logging.getLogger(__name__)


def wait_for_job(glue, job_name: str, run_id: str, poll_seconds: int = 30) -> dict:
    terminal = {"SUCCEEDED", "FAILED", "STOPPED", "TIMEOUT", "ERROR"}
    while True:
        run = glue.get_job_run(JobName=job_name, RunId=run_id)["JobRun"]
        if run["JobRunState"] in terminal:
            return run
        time.sleep(poll_seconds)


def etl_then_crawl(job_name: str, crawler_name: str, job_args: dict) -> None:
    glue = boto3.client("glue")

    run_id = glue.start_job_run(JobName=job_name, Arguments=job_args)["JobRunId"]
    logger.info("Started job %s run %s", job_name, run_id)

    result = wait_for_job(glue, job_name, run_id)
    if result["JobRunState"] != "SUCCEEDED":
        raise RuntimeError(result.get("ErrorMessage", "Job failed"))

    glue.start_crawler(Name=crawler_name)
    logger.info("Started crawler %s after successful ETL", crawler_name)
```

### Paginate Catalog Tables with Schema Export

```python
import json
from pathlib import Path

import boto3


def export_database_schema(database: str, output_dir: str) -> None:
    glue = boto3.client("glue")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    paginator = glue.get_paginator("get_tables")
    for page in paginator.paginate(DatabaseName=database):
        for table in page["TableList"]:
            name = table["Name"]
            payload = {
                "database": database,
                "table": name,
                "columns": table["StorageDescriptor"]["Columns"],
                "partition_keys": table.get("PartitionKeys", []),
                "location": table["StorageDescriptor"]["Location"],
            }
            (out / f"{name}.json").write_text(json.dumps(payload, indent=2))
```

### Production-Ready — Glue Job Wrapper with Retries and Metrics

```python
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class JobRunResult:
    job_name: str
    run_id: str
    state: str
    execution_time: int | None
    error_message: str | None


class GlueJobRunner:
    def __init__(self, region: str = "us-east-1"):
        self.glue = boto3.client("glue", region_name=region)
        self.cloudwatch = boto3.client("cloudwatch", region_name=region)

    def start(self, job_name: str, arguments: dict[str, str]) -> str:
        try:
            return self.glue.start_job_run(JobName=job_name, Arguments=arguments)["JobRunId"]
        except ClientError as exc:
            logger.error("Failed to start %s: %s", job_name, exc.response["Error"]["Message"])
            raise

    def wait(self, job_name: str, run_id: str, poll_seconds: int = 30) -> JobRunResult:
        terminal = {"SUCCEEDED", "FAILED", "STOPPED", "TIMEOUT", "ERROR"}
        while True:
            run = self.glue.get_job_run(JobName=job_name, RunId=run_id)["JobRun"]
            state = run["JobRunState"]
            if state in terminal:
                result = JobRunResult(
                    job_name=job_name,
                    run_id=run_id,
                    state=state,
                    execution_time=run.get("ExecutionTime"),
                    error_message=run.get("ErrorMessage"),
                )
                self._emit_metric(job_name, state, result.execution_time)
                return result
            import time
            time.sleep(poll_seconds)

    def _emit_metric(self, job_name: str, state: str, duration: int | None) -> None:
        self.cloudwatch.put_metric_data(
            Namespace="DataPlatform/Glue",
            MetricData=[
                {
                    "MetricName": "JobRunResult",
                    "Dimensions": [{"Name": "JobName", "Value": job_name}],
                    "Value": 1 if state == "SUCCEEDED" else 0,
                    "Unit": "Count",
                    "Timestamp": datetime.now(timezone.utc),
                }
            ],
        )
        if duration is not None:
            self.cloudwatch.put_metric_data(
                Namespace="DataPlatform/Glue",
                MetricData=[
                    {
                        "MetricName": "JobDurationSeconds",
                        "Dimensions": [{"Name": "JobName", "Value": job_name}],
                        "Value": float(duration),
                        "Unit": "Seconds",
                        "Timestamp": datetime.now(timezone.utc),
                    }
                ],
            )
```

### PySpark DynamicFrame Pattern (Glue Script Context)

```python
# Runs inside a Glue ETL job script (orders_daily.py)
import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext

args = getResolvedOptions(sys.argv, ["JOB_NAME", "dt", "target_bucket"])
sc = SparkContext()
glue_context = GlueContext(sc)
spark = glue_context.spark_session
job = Job(glue_context)
job.init(args["JOB_NAME"], args)

dyf = glue_context.create_dynamic_frame.from_catalog(
    database="raw_lake",
    table_name="orders",
    push_down_predicate=f"dt='{args['dt']}'",
)

# Transform and write partitioned Parquet
df = dyf.toDF().filter("amount > 0")
(
    df.write.mode("overwrite")
    .partitionBy("dt")
    .parquet(f"s3://{args['target_bucket']}/orders/")
)

job.commit()
```

### Batch Register Partitions from S3 Listing

```python
import boto3


def sync_partitions_from_s3(database: str, table: str, s3_prefix: str) -> int:
    glue = boto3.client("glue")
    s3 = boto3.client("s3")

    bucket, _, prefix = s3_prefix.replace("s3://", "").partition("/")
    paginator = s3.get_paginator("list_objects_v2")

    partition_dates = set()
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
        for cp in page.get("CommonPrefixes", []):
            folder = cp["Prefix"].rstrip("/").split("/")[-1]
            if folder.startswith("dt="):
                partition_dates.add(folder.split("=", 1)[1])

    created = 0
    for dt in sorted(partition_dates):
        try:
            glue.create_partition(
                DatabaseName=database,
                TableName=table,
                PartitionInput={
                    "Values": [dt],
                    "StorageDescriptor": {
                        "Location": f"s3://{bucket}/{prefix}dt={dt}/",
                        "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
                        "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
                        "SerdeInfo": {
                            "SerializationLibrary": "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
                        },
                    },
                },
            )
            created += 1
        except glue.exceptions.AlreadyExistsException:
            pass
    return created
```

---

## Security Considerations

- Use **IAM roles** (Lambda, EC2, ECS) instead of long-lived access keys in orchestration scripts.
- Scope Boto3 callers to minimum Glue actions: `StartJobRun`, `GetJobRun`, `CreatePartition`, etc.
- Never log **job arguments** containing PII or connection strings.
- Run orchestration code in the **same region** as Glue jobs to avoid cross-region data transfer surprises.
- Use **`botocore.config.Config`** with adaptive retries for resilient production pipelines.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `EndpointConnectionError` | Wrong region or network | Set `region_name` explicitly; check VPC endpoints |
| `ThrottlingException` | API rate limit | Enable adaptive retries; backoff between polls |
| `ConcurrentRunsExceededException` | Job concurrency cap | Serialize triggers or raise `MaxConcurrentRuns` |
| `AlreadyExistsException` | Duplicate partition | Catch and ignore in idempotent registration |
| Import `awsglue` fails locally | Glue libs not on local machine | Test PySpark logic separately; run Glue libs only on Glue |

---

## Best Practices

- Wrap Glue operations in a **small internal SDK** (`GlueJobRunner`) for consistent logging and metrics.
- Use **paginators** for catalog and job run listing — never assume single-page responses.
- Emit **custom CloudWatch metrics** (`JobDurationSeconds`, `JobRunResult`) for SLA dashboards.
- Keep orchestration logic **separate from PySpark transform logic** in different files/repos.
- Parameterize all job arguments; avoid hardcoded bucket names in Python wrappers.
- Use **Step Functions** for complex state machines; use Boto3 wrappers for simple job+crawl patterns.
- Pin **`boto3`** and **`botocore`** versions in requirements for reproducible deployments.
