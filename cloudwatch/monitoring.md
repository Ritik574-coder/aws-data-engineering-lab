# CloudWatch — Monitoring

## Service Overview

**Amazon CloudWatch** collects metrics, logs, and events from AWS services and custom applications. For data engineering, it is the primary observability layer for Glue job duration, Athena query volume, Lambda errors, and pipeline SLA tracking.

**Common use cases:**
- Dashboard Glue ETL success rates and DPU utilization
- Track Athena `ProcessedBytes` per workgroup for cost control
- Monitor Lambda pipeline function errors and throttles
- Custom metrics for records processed, lag, and data freshness

**When to use it:** From day one in production — every pipeline component should emit metrics and logs queryable in CloudWatch.

---

## AWS CLI Commands

### List Available Metrics (Glue Namespace)

**Purpose:** Discover metric names and dimensions for Glue jobs.

**Command:**

```bash
aws cloudwatch list-metrics \
  --namespace Glue \
  --dimensions Name=JobName,Value=orders-daily-etl
```

**Example Output (abbreviated):**

```json
{
    "Metrics": [
        {"Namespace": "Glue", "MetricName": "glue.driver.aggregate.numCompletedTasks", "Dimensions": [{"Name": "JobName", "Value": "orders-daily-etl"}]},
        {"Namespace": "Glue", "MetricName": "glue.ALL.s3.filesystem.read_bytes", "Dimensions": [{"Name": "JobName", "Value": "orders-daily-etl"}]}
    ]
}
```

---

### Get Metric Statistics

**Purpose:** Retrieve time-series data for a metric (e.g., Glue job duration).

**Command:**

```bash
aws cloudwatch get-metric-statistics \
  --namespace Glue \
  --metric-name glue.driver.aggregate.elapsedTime \
  --dimensions Name=JobName,Value=orders-daily-etl Name=JobRunId,Value=jr_a1b2c3d4 \
  --start-time 2025-03-01T00:00:00Z \
  --end-time 2025-03-02T00:00:00Z \
  --period 300 \
  --statistics Average Maximum
```

**Example Output:**

```json
{
    "Label": "glue.driver.aggregate.elapsedTime",
    "Datapoints": [
        {
            "Timestamp": "2025-03-01T06:15:00+00:00",
            "Average": 861000.0,
            "Maximum": 861000.0,
            "Unit": "Milliseconds"
        }
    ]
}
```

---

### Put Custom Metric

**Purpose:** Publish application-level metrics (records ingested, lag minutes).

**Command:**

```bash
aws cloudwatch put-metric-data \
  --namespace DataPlatform/Pipelines \
  --metric-data '[
    {
      "MetricName": "RecordsIngested",
      "Dimensions": [
        {"Name": "Pipeline", "Value": "orders-ingest"},
        {"Name": "Environment", "Value": "prod"}
      ],
      "Value": 152340,
      "Unit": "Count",
      "Timestamp": "2025-03-01T07:00:00Z"
    }
  ]'
```

**Example Output:** *(empty on success — HTTP 200)*

---

### Get Athena Processed Bytes

**Purpose:** Monitor Athena scan volume by workgroup.

**Command:**

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

**Example Output:**

```json
{
    "Label": "ProcessedBytes",
    "Datapoints": [
        {"Timestamp": "2025-03-01T06:00:00+00:00", "Sum": 5368709120.0, "Unit": "Bytes"}
    ]
}
```

---

### List Dashboards

**Purpose:** Enumerate operational dashboards.

**Command:**

```bash
aws cloudwatch list-dashboards
```

**Example Output:**

```json
{
    "DashboardEntries": [
        {"DashboardName": "DataPlatform-Prod", "LastModified": "2025-02-20T10:00:00+00:00", "Size": 4521}
    ]
}
```

---

### Get Dashboard Body

**Purpose:** Export dashboard JSON for IaC or review.

**Command:**

```bash
aws cloudwatch get-dashboard --dashboard-name DataPlatform-Prod
```

---

### Put Dashboard

**Purpose:** Create or update a pipeline operations dashboard.

**Command:**

```bash
aws cloudwatch put-dashboard \
  --dashboard-name DataPlatform-Prod \
  --dashboard-body '{
    "widgets": [
      {
        "type": "metric",
        "width": 12,
        "height": 6,
        "properties": {
          "title": "Lambda Pipeline Errors",
          "metrics": [
            ["AWS/Lambda", "Errors", "FunctionName", "s3-landing-validator", {"stat": "Sum"}]
          ],
          "period": 300,
          "region": "us-east-1",
          "view": "timeSeries"
        }
      }
    ]
  }'
```

---

## Advanced Commands

### Metric Math — Error Rate

```bash
aws cloudwatch get-metric-data \
  --metric-data-queries '[
    {
      "Id": "errors",
      "MetricStat": {
        "Metric": {
          "Namespace": "AWS/Lambda",
          "MetricName": "Errors",
          "Dimensions": [{"Name": "FunctionName", "Value": "s3-landing-validator"}]
        },
        "Period": 300,
        "Stat": "Sum"
      }
    },
    {
      "Id": "invocations",
      "MetricStat": {
        "Metric": {
          "Namespace": "AWS/Lambda",
          "MetricName": "Invocations",
          "Dimensions": [{"Name": "FunctionName", "Value": "s3-landing-validator"}]
        },
        "Period": 300,
        "Stat": "Sum"
      }
    },
    {
      "Id": "error_rate",
      "Expression": "100 * errors / invocations",
      "Label": "Error Rate %",
      "ReturnData": true
    }
  ]' \
  --start-time 2025-03-01T00:00:00Z \
  --end-time 2025-03-02T00:00:00Z
```

### Search Metrics Across Namespaces

```bash
aws cloudwatch list-metrics \
  --metric-name Errors \
  --query 'Metrics[?Namespace==`AWS/Lambda`].Dimensions' \
  --output table
```

### Enable Contributor Insights (via CLI reference)

```bash
aws cloudwatch put-insight-rule \
  --rule-name lambda-throttle-insights \
  --rule-definition '{
    "Schema": {"Name": "CloudWatchLogRule", "Version": 1},
    "LogFormat": "CLF",
    "Fields": {"3": "FunctionName"},
    "Contribution": {"Keys": ["FunctionName"]},
    "AggregateOn": "Count"
  }'
```

---

## Python Boto3 Examples

### Basic — Publish Custom Metric

```python
from datetime import datetime, timezone

import boto3

cloudwatch = boto3.client("cloudwatch")

cloudwatch.put_metric_data(
    Namespace="DataPlatform/Pipelines",
    MetricData=[
        {
            "MetricName": "PipelineLagMinutes",
            "Dimensions": [
                {"Name": "Pipeline", "Value": "orders-ingest"},
                {"Name": "Environment", "Value": "prod"},
            ],
            "Value": 12.5,
            "Unit": "None",
            "Timestamp": datetime.now(timezone.utc),
        }
    ],
)
```

### Production-Ready — Metrics Emitter with Batch Flush

```python
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class MetricsBuffer:
    namespace: str
    _buffer: list[dict[str, Any]] = field(default_factory=list)
    _client: Any = field(default_factory=lambda: boto3.client("cloudwatch"))
    max_batch: int = 20

    def put(
        self,
        metric_name: str,
        value: float,
        unit: str = "Count",
        dimensions: dict[str, str] | None = None,
    ) -> None:
        entry: dict[str, Any] = {
            "MetricName": metric_name,
            "Value": value,
            "Unit": unit,
            "Timestamp": datetime.now(timezone.utc),
        }
        if dimensions:
            entry["Dimensions"] = [{"Name": k, "Value": v} for k, v in dimensions.items()]
        self._buffer.append(entry)
        if len(self._buffer) >= self.max_batch:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        try:
            self._client.put_metric_data(Namespace=self.namespace, MetricData=self._buffer)
            logger.debug("Flushed %d metrics to %s", len(self._buffer), self.namespace)
        except ClientError as exc:
            logger.error("Metric flush failed: %s", exc.response["Error"]["Message"])
            raise
        finally:
            self._buffer.clear()
```

### Query Glue Job Duration Trend

```python
import boto3
from datetime import datetime, timedelta, timezone


def get_glue_job_avg_duration(job_name: str, hours: int = 24) -> float | None:
    cw = boto3.client("cloudwatch")
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)

    resp = cw.get_metric_statistics(
        Namespace="Glue",
        MetricName="glue.driver.aggregate.elapsedTime",
        Dimensions=[{"Name": "JobName", "Value": job_name}],
        StartTime=start,
        EndTime=end,
        Period=3600,
        Statistics=["Average"],
    )
    points = resp.get("Datapoints", [])
    if not points:
        return None
    return sum(p["Average"] for p in points) / len(points) / 1000  # seconds
```

---

## Security Considerations

- Restrict **`cloudwatch:PutMetricData`** to approved namespaces via IAM condition keys.
- Use **resource-level permissions** for dashboards and alarms in shared accounts.
- Encrypt **CloudWatch Logs** with KMS for pipelines handling sensitive data.
- Avoid putting **PII** in metric dimensions or custom metric names.
- Enable **cross-account observability** only with explicit trust and data boundaries.

---

## Troubleshooting

| Error / Symptom | Root Cause | Resolution |
|-----------------|------------|------------|
| No datapoints returned | Wrong dimension or time range | Verify dimensions match; extend time window |
| `AccessDenied` on PutMetricData | IAM policy gap | Grant `cloudwatch:PutMetricData` on `*` or namespace condition |
| Metrics delayed up to 15 min | Normal CloudWatch behavior | Use `StorageResolution: 1` for high-resolution (extra cost) |
| Dashboard empty | Wrong region in widget | Set `region` in dashboard JSON to deployment region |
| Custom metrics missing dimensions | Dimension cardinality limits | Limit unique dimension combinations (< 1000 recommended) |

---

## Best Practices

- Use consistent namespace hierarchy: `DataPlatform/<Service>/<Metric>`.
- Standardize dimensions: `Environment`, `Pipeline`, `Team`, `DataDomain`.
- Build **one dashboard per environment** with Glue, Lambda, Athena, and SQS widgets.
- Emit **business metrics** (records processed, freshness lag) alongside infrastructure metrics.
- Use **metric math** for error rates and SLA percentages instead of manual calculation.
- Set **period** to match alarm evaluation (typically 60s or 300s).
- Export dashboards as JSON in **Git** for reproducibility.
- Review **Athena ProcessedBytes** weekly to identify cost optimization targets.
