# Glue — Jobs

## Service Overview

**AWS Glue** is a fully managed extract, transform, and load (ETL) service. **Glue Jobs** run Apache Spark (PySpark or Scala) or Python shell scripts on serverless compute to transform data in S3, JDBC sources, and other data stores.

**Common use cases:**
- Batch ETL from raw S3 landing zones to curated Parquet tables
- Incremental loads with bookmarking and partition overwrite
- Data quality checks and schema normalization before Athena queries
- JDBC-to-S3 replication (RDS, Redshift, on-prem databases via connections)

**When to use it:** When you need managed Spark ETL without operating EMR clusters, with native integration to the Glue Data Catalog, job bookmarks, and workflow orchestration.

---

## AWS CLI Commands

### List Glue Jobs

**Purpose:** List all ETL job definitions in the account.

**Command:**

```bash
aws glue list-jobs --max-results 50
```

**Example Output:**

```json
{
    "JobNames": [
        "orders-daily-etl",
        "customers-cdc-merge",
        "events-parquet-compaction"
    ],
    "NextToken": "eyJ..."
}
```

**Explanation:** Returns job names only. Use `get-job` for full configuration. Requires `glue:ListJobs`.

---

### Get Job Definition

**Purpose:** Inspect job configuration (role, script location, worker type, bookmarks).

**Command:**

```bash
aws glue get-job --job-name orders-daily-etl
```

**Example Output (abbreviated):**

```json
{
    "Job": {
        "Name": "orders-daily-etl",
        "Role": "arn:aws:iam::123456789012:role/GlueETLRole",
        "Command": {
            "Name": "glueetl",
            "ScriptLocation": "s3://etl-artifacts/glue/scripts/orders_daily.py",
            "PythonVersion": "3"
        },
        "DefaultArguments": {
            "--job-bookmark-option": "job-bookmark-enable",
            "--enable-metrics": "true",
            "--TempDir": "s3://etl-staging/glue/temp/"
        },
        "GlueVersion": "4.0",
        "NumberOfWorkers": 5,
        "WorkerType": "G.1X",
        "MaxRetries": 1,
        "Timeout": 120
    }
}
```

---

### Start a Job Run

**Purpose:** Trigger an on-demand ETL run (manual backfill or ad-hoc reprocessing).

**Command:**

```bash
aws glue start-job-run \
  --job-name orders-daily-etl \
  --arguments '{
    "--dt": "2025-03-01",
    "--target_bucket": "analytics-curated",
    "--enable-bookmark": "true"
  }'
```

**Example Output:**

```json
{
    "JobRunId": "jr_a1b2c3d4e5f6789012345678"
}
```

**Explanation:** Returns a unique `JobRunId`. Poll status with `get-job-run` or monitor in CloudWatch.

---

### Get Job Run Status

**Purpose:** Check whether a run succeeded, failed, or is still running.

**Command:**

```bash
aws glue get-job-run \
  --job-name orders-daily-etl \
  --run-id jr_a1b2c3d4e5f6789012345678
```

**Example Output (abbreviated):**

```json
{
    "JobRun": {
        "Id": "jr_a1b2c3d4e5f6789012345678",
        "JobName": "orders-daily-etl",
        "JobRunState": "SUCCEEDED",
        "StartedOn": "2025-03-01T06:00:12.000+00:00",
        "CompletedOn": "2025-03-01T06:14:33.000+00:00",
        "ExecutionTime": 861,
        "MaxCapacity": 5.0,
        "LogGroupName": "/aws-glue/jobs/output"
    }
}
```

**Job run states:** `STARTING`, `RUNNING`, `STOPPING`, `STOPPED`, `SUCCEEDED`, `FAILED`, `TIMEOUT`, `ERROR`.

---

### Stop a Running Job

**Purpose:** Cancel a long-running or stuck job run.

**Command:**

```bash
aws glue batch-stop-job-run \
  --job-name orders-daily-etl \
  --job-run-ids jr_a1b2c3d4e5f6789012345678
```

**Example Output:**

```json
{
    "SuccessfulSubmissions": ["jr_a1b2c3d4e5f6789012345678"],
    "Errors": []
}
```

---

### Create a Job

**Purpose:** Define a new ETL job (typically done via IaC; CLI useful for prototyping).

**Command:**

```bash
aws glue create-job \
  --name orders-daily-etl \
  --role GlueETLRole \
  --command Name=glueetl,ScriptLocation=s3://etl-artifacts/glue/scripts/orders_daily.py,PythonVersion=3 \
  --default-arguments '{
    "--job-bookmark-option": "job-bookmark-enable",
    "--enable-metrics": "true",
    "--enable-continuous-cloudwatch-log": "true",
    "--TempDir": "s3://etl-staging/glue/temp/",
    "--datalake-formats": "delta"
  }' \
  --glue-version "4.0" \
  --worker-type G.1X \
  --number-of-workers 5 \
  --max-retries 1 \
  --timeout 120
```

**Example Output:**

```json
{
    "Name": "orders-daily-etl"
}
```

---

### Update Job Configuration

**Purpose:** Change worker count, timeout, or default arguments without recreating the job.

**Command:**

```bash
aws glue update-job \
  --job-name orders-daily-etl \
  --job-update '{
    "Role": "arn:aws:iam::123456789012:role/GlueETLRole",
    "Command": {
      "Name": "glueetl",
      "ScriptLocation": "s3://etl-artifacts/glue/scripts/orders_daily.py",
      "PythonVersion": "3"
    },
    "DefaultArguments": {
      "--job-bookmark-option": "job-bookmark-enable",
      "--enable-metrics": "true"
    },
    "GlueVersion": "4.0",
    "NumberOfWorkers": 10,
    "WorkerType": "G.2X",
    "MaxRetries": 2,
    "Timeout": 180
  }'
```

---

### List Job Runs (History)

**Purpose:** Audit recent runs for SLA monitoring or failure analysis.

**Command:**

```bash
aws glue get-job-runs \
  --job-name orders-daily-etl \
  --max-results 10
```

**Example Output (abbreviated):**

```json
{
    "JobRuns": [
        {
            "Id": "jr_a1b2c3d4e5f6789012345678",
            "JobRunState": "SUCCEEDED",
            "StartedOn": "2025-03-01T06:00:12.000+00:00",
            "ExecutionTime": 861
        },
        {
            "Id": "jr_9876543210fedcba9876543210",
            "JobRunState": "FAILED",
            "ErrorMessage": "AnalysisException: Path does not exist: s3://raw/orders/dt=2025-02-28/"
        }
    ]
}
```

---

## Advanced Commands

### Filter Failed Runs with JMESPath

```bash
aws glue get-job-runs \
  --job-name orders-daily-etl \
  --max-results 50 \
  --query 'JobRuns[?JobRunState==`FAILED`].{RunId:Id,Error:ErrorMessage,Started:StartedOn}' \
  --output table
```

### Start Job with Notification Properties

```bash
aws glue start-job-run \
  --job-name orders-daily-etl \
  --notification-property NotifyDelayAfter=15 \
  --arguments '{"--dt": "2025-03-01"}'
```

### Reset Job Bookmark (Full Reprocess)

```bash
aws glue reset-job-bookmark --job-name orders-daily-etl
```

**Warning:** The next run reprocesses all source data. Use only for backfills or bookmark corruption recovery.

---

### Concurrent Runs and Job Queuing

```bash
aws glue put-job --job-name orders-daily-etl \
  --job-update '{
    "Role": "arn:aws:iam::123456789012:role/GlueETLRole",
    "Command": {"Name": "glueetl", "ScriptLocation": "s3://etl-artifacts/glue/scripts/orders_daily.py", "PythonVersion": "3"},
    "ExecutionProperty": {"MaxConcurrentRuns": 3},
    "GlueVersion": "4.0",
    "NumberOfWorkers": 5,
    "WorkerType": "G.1X"
  }'
```

### Tag Jobs for Cost Allocation

```bash
aws glue tag-resource \
  --resource-arn arn:aws:glue:us-east-1:123456789012:job/orders-daily-etl \
  --tags-to-add Environment=prod,Team=analytics,DataDomain=orders
```

---

## Python Boto3 Examples

### Basic — Start Job and Poll Until Complete

```python
import time

import boto3

glue = boto3.client("glue")

job_name = "orders-daily-etl"
response = glue.start_job_run(
    JobName=job_name,
    Arguments={"--dt": "2025-03-01"},
)
run_id = response["JobRunId"]

while True:
    run = glue.get_job_run(JobName=job_name, RunId=run_id)["JobRun"]
    state = run["JobRunState"]
    print(f"Run {run_id}: {state}")
    if state in {"SUCCEEDED", "FAILED", "STOPPED", "TIMEOUT", "ERROR"}:
        break
    time.sleep(30)

if state != "SUCCEEDED":
    raise RuntimeError(f"Job failed: {run.get('ErrorMessage')}")
```

### Production-Ready — Idempotent Job Trigger with Logging

```python
import logging
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def start_glue_job(
    job_name: str,
    arguments: dict[str, str],
    region: str = "us-east-1",
) -> str:
    glue = boto3.client("glue", region_name=region)

    try:
        response = glue.start_job_run(JobName=job_name, Arguments=arguments)
        run_id = response["JobRunId"]
        logger.info(
            "Started Glue job %s run_id=%s args=%s at %s",
            job_name,
            run_id,
            arguments,
            datetime.now(timezone.utc).isoformat(),
        )
        return run_id
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "ConcurrentRunsExceededException":
            logger.warning("Concurrent run limit reached for %s", job_name)
        raise
```

---

## Security Considerations

- Attach a **dedicated IAM role** to each job with least privilege: S3 prefixes, Glue Catalog tables, Secrets Manager secrets, and KMS keys only as needed.
- Store scripts and libraries in a **private S3 bucket** with SSE-KMS; block public access.
- Use **Glue connections** with Secrets Manager for JDBC credentials — never hardcode passwords in scripts or job arguments.
- Enable **VPC connections** when accessing private RDS/Redshift endpoints; restrict security groups to minimum ports.
- Enable **CloudWatch Logs** and **Job metrics** for audit trails; restrict log access via IAM.

---

## Troubleshooting

| Error / Symptom | Root Cause | Resolution |
|-----------------|------------|------------|
| `ConcurrentRunsExceededException` | Too many simultaneous runs | Increase `MaxConcurrentRuns` or serialize triggers via Step Functions |
| `EntityNotFoundException` | Job or script path missing | Verify job name and `ScriptLocation` S3 URI |
| `AccessDenied` on S3 | Glue role lacks S3 permissions | Add `s3:GetObject`/`PutObject` on source and target prefixes |
| Job stuck in `RUNNING` | Spark shuffle or skew | Increase workers; repartition; check CloudWatch driver logs |
| Bookmark not advancing | Source path changed or bookmark disabled | Confirm `--job-bookmark-option`; avoid renaming source keys |
| `OutOfMemoryError` | Insufficient executor memory | Switch to `G.2X` workers or reduce partition size |
| JDBC connection timeout | SG/VPC misconfiguration | Verify Glue connection subnet, SG rules, and RDS accessibility |

---

## Best Practices

- Use **Glue 4.0+** with **job bookmarks** for incremental S3/JDBC ingestion.
- Write outputs as **partitioned Parquet** (`dt=`, `hour=`) for Athena performance.
- Set **`--enable-metrics`** and **`--enable-continuous-cloudwatch-log`** on all production jobs.
- Right-size workers: start with `G.1X` and scale based on DPU-hours in CloudWatch; use `G.2X` for memory-heavy joins.
- Manage job definitions with **CloudFormation/Terraform**; use CLI for operational tasks (start, stop, status).
- Implement **dead-letter patterns**: on failure, write bad records to a quarantine prefix and alert via SNS.
- Tag jobs with `Environment`, `Team`, and `DataDomain` for cost allocation in Cost Explorer.
- Use **Step Functions** or **EventBridge** schedules instead of cron on EC2 for orchestration.
