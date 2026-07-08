# CloudWatch — Python Boto3 Examples

## Service Overview

Boto3 provides `cloudwatch` and `logs` clients for building observability automation — custom metric emitters, log shippers, alarm provisioners, and pipeline health dashboards. Data platform teams use these patterns in Lambda, ECS tasks, and CI/CD pipelines.

**Common use cases:**
- Emit batch processing metrics from Glue job completion handlers
- Automate alarm creation when new pipelines deploy
- Run Logs Insights queries from incident response scripts
- Build internal SLA dashboards programmatically

**When to use it:** When observability must be integrated into deployment pipelines or custom orchestration rather than configured manually in the Console.

---

## AWS CLI Commands

### Verify CloudWatch API Access

**Purpose:** Confirm credentials can publish metrics.

**Command:**

```bash
aws cloudwatch list-metrics --namespace DataPlatform/Pipelines --max-items 5
```

**Example Output:**

```json
{
    "Metrics": [
        {
            "Namespace": "DataPlatform/Pipelines",
            "MetricName": "RecordsIngested",
            "Dimensions": [{"Name": "Pipeline", "Value": "orders-ingest"}]
        }
    ]
}
```

---

### Get Alarm State for Script Gating

**Purpose:** Check if deployment should proceed based on alarm state.

**Command:**

```bash
aws cloudwatch describe-alarms \
  --alarm-names glue-orders-job-failed-prod \
  --query 'MetricAlarms[0].StateValue' \
  --output text
```

**Example Output:**

```
OK
```

---

## Advanced Commands

### Batch Put Metrics (CLI reference — use Boto3 for batches > 20)

```bash
# CloudWatch accepts up to 20 metrics per PutMetricData call
aws cloudwatch put-metric-data \
  --namespace DataPlatform/Pipelines \
  --metric-data file://metrics-batch.json
```

---

## Python Boto3 Examples

### Unified Observability Client

```python
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class PipelineObservability:
    namespace: str = "DataPlatform/Pipelines"
    region: str = "us-east-1"
    _metrics: list[dict[str, Any]] = field(default_factory=list)
    _cw: Any = field(init=False)
    _logs: Any = field(init=False)

    def __post_init__(self):
        self._cw = boto3.client("cloudwatch", region_name=self.region)
        self._logs = boto3.client("logs", region_name=self.region)

    def record(
        self,
        metric: str,
        value: float,
        unit: str = "Count",
        dimensions: dict[str, str] | None = None,
    ) -> None:
        entry: dict[str, Any] = {
            "MetricName": metric,
            "Value": value,
            "Unit": unit,
            "Timestamp": datetime.now(timezone.utc),
        }
        if dimensions:
            entry["Dimensions"] = [{"Name": k, "Value": v} for k, v in dimensions.items()]
        self._metrics.append(entry)
        if len(self._metrics) >= 20:
            self.flush_metrics()

    def flush_metrics(self) -> None:
        if not self._metrics:
            return
        self._cw.put_metric_data(Namespace=self.namespace, MetricData=self._metrics)
        logger.debug("Flushed %d metrics", len(self._metrics))
        self._metrics.clear()

    def log(self, log_group: str, log_stream: str, message: dict) -> None:
        ts = int(time.time() * 1000)
        body = json.dumps({**message, "ts": datetime.now(timezone.utc).isoformat()})
        try:
            self._logs.create_log_stream(logGroupName=log_group, logStreamName=log_stream)
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ResourceAlreadyExistsException":
                if exc.response["Error"]["Code"] != "ResourceNotFoundException":
                    raise
                self._logs.create_log_group(logGroupName=log_group)
                self._logs.create_log_stream(logGroupName=log_group, logStreamName=log_stream)

        self._logs.put_log_events(
            logGroupName=log_group,
            logStreamName=log_stream,
            logEvents=[{"timestamp": ts, "message": body}],
        )
```

### Glue Job Completion Hook

```python
import boto3


def on_glue_job_complete(job_name: str, run_id: str, state: str, duration_sec: int | None) -> None:
    obs = PipelineObservability()
    dims = {"JobName": job_name, "Environment": "prod"}

    obs.record("JobRunResult", 1 if state == "SUCCEEDED" else 0, dimensions=dims)
    if duration_sec is not None:
        obs.record("JobDurationSeconds", float(duration_sec), unit="Seconds", dimensions=dims)
    obs.flush_metrics()

    obs.log(
        log_group="/data-platform/glue-events",
        log_stream=run_id,
        message={"job": job_name, "run_id": run_id, "state": state, "duration_sec": duration_sec},
    )
```

### Provision Standard Pipeline Alarms

```python
import boto3


def provision_pipeline_alarms(
    pipeline: str,
    sns_arn: str,
    lag_threshold_minutes: float = 60,
) -> None:
    cw = boto3.client("cloudwatch")
    env = "prod"
    dims = [
        {"Name": "Pipeline", "Value": pipeline},
        {"Name": "Environment", "Value": env},
    ]

    alarms = [
        {
            "AlarmName": f"{pipeline}-lag-{env}",
            "MetricName": "PipelineLagMinutes",
            "Threshold": lag_threshold_minutes,
            "ComparisonOperator": "GreaterThanThreshold",
            "Statistic": "Maximum",
        },
        {
            "AlarmName": f"{pipeline}-zero-records-{env}",
            "MetricName": "RecordsIngested",
            "Threshold": 1,
            "ComparisonOperator": "LessThanThreshold",
            "Statistic": "Sum",
            "TreatMissingData": "breaching",
        },
    ]

    for spec in alarms:
        cw.put_metric_alarm(
            AlarmName=spec["AlarmName"],
            Namespace="DataPlatform/Pipelines",
            MetricName=spec["MetricName"],
            Dimensions=dims,
            Statistic=spec["Statistic"],
            Period=300,
            EvaluationPeriods=2,
            Threshold=spec["Threshold"],
            ComparisonOperator=spec["ComparisonOperator"],
            TreatMissingData=spec.get("TreatMissingData", "notBreaching"),
            AlarmActions=[sns_arn],
            OKActions=[sns_arn],
        )
```

### Logs Insights — Pipeline Error Report

```python
import boto3
import time
from datetime import datetime, timedelta, timezone


def pipeline_error_report(log_groups: list[str], hours: int = 24) -> list[dict]:
    logs = boto3.client("logs")
    end = int(datetime.now(timezone.utc).timestamp())
    start = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())

    qid = logs.start_query(
        logGroupNames=log_groups,
        startTime=start,
        endTime=end,
        queryString="""
            fields @timestamp, @logStream, @message
            | filter @message like /ERROR|FAILED|Exception/
            | stats count() as error_count by @logStream
            | sort error_count desc
            | limit 20
        """,
    )["queryId"]

    while True:
        result = logs.get_query_results(queryId=qid)
        if result["status"] in {"Complete", "Failed", "Cancelled"}:
            break
        time.sleep(2)

    rows = []
    for row in result.get("results", []):
        parsed = {col["field"]: col["value"] for col in row}
        rows.append(parsed)
    return rows
```

### Dashboard as Code

```python
import json
import boto3


def deploy_dashboard(name: str, pipeline: str, region: str = "us-east-1") -> None:
    cw = boto3.client("cloudwatch", region_name=region)
    body = {
        "widgets": [
            {
                "type": "metric",
                "width": 12,
                "height": 6,
                "properties": {
                    "title": f"{pipeline} — Records Ingested",
                    "metrics": [
                        ["DataPlatform/Pipelines", "RecordsIngested", "Pipeline", pipeline, "Environment", "prod"]
                    ],
                    "period": 300,
                    "stat": "Sum",
                    "region": region,
                    "view": "timeSeries",
                },
            },
            {
                "type": "metric",
                "width": 12,
                "height": 6,
                "properties": {
                    "title": f"{pipeline} — Lag Minutes",
                    "metrics": [
                        ["DataPlatform/Pipelines", "PipelineLagMinutes", "Pipeline", pipeline, "Environment", "prod"]
                    ],
                    "period": 300,
                    "stat": "Maximum",
                    "region": region,
                    "view": "timeSeries",
                },
            },
        ]
    }
    cw.put_dashboard(DashboardName=name, DashboardBody=json.dumps(body))
```

---

## Security Considerations

- Scope IAM policies: **`cloudwatch:PutMetricData`** only for approved namespaces via conditions.
- Logs Insights queries can expose sensitive data — restrict **`logs:StartQuery`** to trusted roles.
- Do not embed **access keys** in observability scripts; use roles and SSO.
- Sanitize log messages before **`put_log_events`** — redact PII at source.
- Encrypt log groups at rest when shipping pipeline audit logs.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `LimitExceededException` on PutMetricData | >20 metrics per call | Batch in groups of 20 |
| Logs Insights `Running` forever | Large log volume / complex query | Narrow time range; add filters early in query |
| `InvalidParameterException` on alarm | Bad metric math expression | Validate expression in Metrics console first |
| Duplicate log events rejected | Same millisecond timestamp | Increment timestamps by 1ms per event |
| Dashboard not updating | Cached widget | Verify `put_dashboard` succeeded; check region |

---

## Best Practices

- Encapsulate metrics + logs in a single **`PipelineObservability`** helper used across all pipeline code.
- Always **`flush_metrics()`** in `finally` blocks before Lambda/process exit.
- Provision alarms **in the same CI/CD step** that deploys the pipeline.
- Use **Logs Insights** saved queries for repeatable incident runbooks.
- Version **dashboard JSON** in Git; deploy with `put_dashboard` on merge to main.
- Include standard dimensions on every metric: `Pipeline`, `Environment`, `Team`.
- Test observability in staging by injecting controlled failures before prod cutover.
