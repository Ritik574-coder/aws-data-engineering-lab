# CloudWatch — Alarms

## Service Overview

**Amazon CloudWatch Alarms** watch metrics and trigger actions when thresholds are breached. In data engineering, alarms notify teams of failed Glue jobs, Lambda errors, Athena cost spikes, and pipeline freshness SLA violations.

**Common use cases:**
- Alert when a Glue job fails or exceeds duration baseline
- Notify on-call when Lambda pipeline error rate exceeds 1%
- Alarm on Athena `ProcessedBytes` daily sum exceeding budget
- Composite alarms for multi-step pipeline failure detection

**When to use it:** For every production pipeline SLA — alarms convert passive logs into proactive incident response via SNS, PagerDuty, or Slack integrations.

---

## AWS CLI Commands

### Put Metric Alarm — Lambda Errors

**Purpose:** Create an alarm when Lambda errors exceed threshold.

**Command:**

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name lambda-s3-validator-errors-prod \
  --alarm-description "Alert when s3-landing-validator errors > 5 in 5 min" \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=s3-landing-validator \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --treat-missing-data notBreaching \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:data-platform-alerts
```

**Example Output:** *(empty on success — HTTP 200)*

---

### Describe Alarms

**Purpose:** List configured alarms and their states.

**Command:**

```bash
aws cloudwatch describe-alarms \
  --alarm-name-prefix lambda- \
  --state-value ALARM \
  --max-records 20
```

**Example Output (abbreviated):**

```json
{
    "MetricAlarms": [
        {
            "AlarmName": "lambda-s3-validator-errors-prod",
            "StateValue": "ALARM",
            "StateReason": "Threshold Crossed: 1 datapoint [8.0 (01/03/25 06:05:00)] was greater than the threshold (5.0).",
            "MetricName": "Errors",
            "Namespace": "AWS/Lambda",
            "Threshold": 5.0,
            "ComparisonOperator": "GreaterThanThreshold"
        }
    ]
}
```

**Alarm states:** `OK`, `ALARM`, `INSUFFICIENT_DATA`.

---

### Put Metric Alarm — Custom Pipeline Lag

**Purpose:** Alarm on a custom metric for data freshness.

**Command:**

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name orders-ingest-lag-prod \
  --namespace DataPlatform/Pipelines \
  --metric-name PipelineLagMinutes \
  --dimensions Name=Pipeline,Value=orders-ingest Name=Environment,Value=prod \
  --statistic Maximum \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 60 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:data-platform-alerts \
  --ok-actions arn:aws:sns:us-east-1:123456789012:data-platform-alerts
```

---

### Put Composite Alarm

**Purpose:** Trigger when any step in a multi-job pipeline fails.

**Command:**

```bash
aws cloudwatch put-composite-alarm \
  --alarm-name pipeline-orders-failure-composite \
  --alarm-description "Fires if ingest OR transform step alarms" \
  --alarm-rule "ALARM(lambda-s3-validator-errors-prod) OR ALARM(glue-orders-job-failed-prod)" \
  --actions-enabled \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:data-platform-alerts
```

---

### Set Alarm State (Testing)

**Purpose:** Manually test SNS routing without triggering real failures.

**Command:**

```bash
aws cloudwatch set-alarm-state \
  --alarm-name lambda-s3-validator-errors-prod \
  --state-value ALARM \
  --state-reason "Manual test of alerting pipeline"
```

---

### Enable Alarm Actions

**Purpose:** Re-enable actions after maintenance (actions may be suppressed during deploys).

**Command:**

```bash
aws cloudwatch enable-alarm-actions \
  --alarm-names lambda-s3-validator-errors-prod orders-ingest-lag-prod
```

---

### Delete Alarm

**Purpose:** Remove obsolete alarms.

**Command:**

```bash
aws cloudwatch delete-alarms --alarm-names old-test-alarm
```

---

### Put Anomaly Detection Alarm

**Purpose:** Detect unusual Glue job duration without static thresholds.

**Command:**

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name glue-orders-duration-anomaly \
  --alarm-description "Anomaly detection on Glue job duration" \
  --metrics '[
    {
      "Id": "m1",
      "ReturnData": true,
      "MetricStat": {
        "Metric": {
          "Namespace": "Glue",
          "MetricName": "glue.driver.aggregate.elapsedTime",
          "Dimensions": [{"Name": "JobName", "Value": "orders-daily-etl"}]
        },
        "Period": 3600,
        "Stat": "Average"
      }
    },
    {
      "Id": "ad1",
      "Expression": "ANOMALY_DETECTION_BAND(m1, 2)"
    }
  ]' \
  --threshold-metric-id ad1 \
  --comparison-operator GreaterThanUpperThreshold \
  --evaluation-periods 2 \
  --datapoints-to-alarm 2 \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:data-platform-alerts
```

---

## Advanced Commands

### Describe Alarm History

```bash
aws cloudwatch describe-alarm-history \
  --alarm-name lambda-s3-validator-errors-prod \
  --history-item-type StateUpdate \
  --max-records 10 \
  --query 'AlarmHistoryItems[].{Time:Timestamp,Reason:HistorySummary}' \
  --output table
```

### Metric Math Alarm — Error Rate

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name lambda-validator-error-rate \
  --evaluation-periods 2 \
  --datapoints-to-alarm 2 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --metrics '[
    {"Id": "errors", "MetricStat": {"Metric": {"Namespace": "AWS/Lambda", "MetricName": "Errors", "Dimensions": [{"Name": "FunctionName", "Value": "s3-landing-validator"}]}, "Period": 300, "Stat": "Sum"}},
    {"Id": "invocations", "MetricStat": {"Metric": {"Namespace": "AWS/Lambda", "MetricName": "Invocations", "Dimensions": [{"Name": "FunctionName", "Value": "s3-landing-validator"}]}, "Period": 300, "Stat": "Sum"}},
    {"Id": "error_rate", "Expression": "100 * errors / IF(invocations > 0, invocations, 1)", "ReturnData": true}
  ]'
```

### Tag Alarms

```bash
aws cloudwatch tag-resource \
  --resource-arn arn:aws:cloudwatch:us-east-1:123456789012:alarm:lambda-s3-validator-errors-prod \
  --tags Key=Environment,Value=prod Key=Team,Value=data-platform
```

---

## Python Boto3 Examples

### Basic — Create SNS-Backed Alarm

```python
import boto3

cloudwatch = boto3.client("cloudwatch")

cloudwatch.put_metric_alarm(
    AlarmName="glue-orders-job-failed-prod",
    AlarmDescription="Glue job failure detected via custom metric",
    Namespace="DataPlatform/Glue",
    MetricName="JobRunResult",
    Dimensions=[
        {"Name": "JobName", "Value": "orders-daily-etl"},
        {"Name": "Environment", "Value": "prod"},
    ],
    Statistic="Sum",
    Period=300,
    EvaluationPeriods=1,
    Threshold=0,
    ComparisonOperator="LessThanOrEqualToThreshold",
    TreatMissingData="breaching",
    AlarmActions=["arn:aws:sns:us-east-1:123456789012:data-platform-alerts"],
)
```

### Production-Ready — Alarm Manager

```python
import logging
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class AlarmSpec:
    name: str
    namespace: str
    metric_name: str
    dimensions: dict[str, str]
    threshold: float
    comparison: str = "GreaterThanThreshold"
    period: int = 300
    evaluation_periods: int = 2
    statistic: str = "Sum"
    sns_topic_arn: str = ""


class AlarmManager:
    def __init__(self, region: str = "us-east-1"):
        self.cw = boto3.client("cloudwatch", region_name=region)

    def upsert(self, spec: AlarmSpec) -> None:
        kwargs = {
            "AlarmName": spec.name,
            "Namespace": spec.namespace,
            "MetricName": spec.metric_name,
            "Dimensions": [{"Name": k, "Value": v} for k, v in spec.dimensions.items()],
            "Statistic": spec.statistic,
            "Period": spec.period,
            "EvaluationPeriods": spec.evaluation_periods,
            "Threshold": spec.threshold,
            "ComparisonOperator": spec.comparison,
            "TreatMissingData": "notBreaching",
        }
        if spec.sns_topic_arn:
            kwargs["AlarmActions"] = [spec.sns_topic_arn]
            kwargs["OKActions"] = [spec.sns_topic_arn]

        try:
            self.cw.put_metric_alarm(**kwargs)
            logger.info("Upserted alarm %s", spec.name)
        except ClientError as exc:
            logger.error("Alarm upsert failed: %s", exc.response["Error"]["Message"])
            raise

    def suppress_during_deploy(self, alarm_names: list[str]) -> None:
        self.cw.disable_alarm_actions(AlarmNames=alarm_names)
        logger.info("Disabled actions for %d alarms", len(alarm_names))

    def restore_after_deploy(self, alarm_names: list[str]) -> None:
        self.cw.enable_alarm_actions(AlarmNames=alarm_names)
        logger.info("Re-enabled actions for %d alarms", len(alarm_names))
```

### Check Alarm States for Pipeline Gate

```python
import boto3


def any_alarms_firing(alarm_names: list[str]) -> list[str]:
    cw = boto3.client("cloudwatch")
    resp = cw.describe_alarms(AlarmNames=alarm_names, StateValue="ALARM")
    return [a["AlarmName"] for a in resp.get("MetricAlarms", [])]
```

---

## Security Considerations

- Restrict **`cloudwatch:PutMetricAlarm`** and **`cloudwatch:DeleteAlarms`** to platform/IaC roles.
- SNS topics for alarms should enforce **HTTPS subscriptions** and least-privilege publish policies.
- Avoid alarm descriptions containing **internal system details** visible to broad IAM users.
- Use **composite alarms** to reduce alert noise — do not page on every intermediate metric.
- Test alarms with **`set-alarm-state`** in non-prod before wiring to PagerDuty.

---

## Troubleshooting

| Error / Symptom | Root Cause | Resolution |
|-----------------|------------|------------|
| Alarm stuck in `INSUFFICIENT_DATA` | Metric not published or wrong dimensions | Verify metric exists with `get-metric-statistics` |
| SNS not receiving notifications | Missing `alarm-actions` or disabled actions | Run `enable-alarm-actions`; verify SNS topic policy |
| False positives overnight | Low traffic causes statistic noise | Increase `evaluation-periods`; use anomaly detection |
| Composite alarm never fires | Rule syntax error | Validate rule: `ALARM(name1) OR ALARM(name2)` |
| Alarm fires but job succeeded | Custom metric inverted (0=fail) | Fix metric value logic in pipeline code |
| Too many alerts | Threshold too sensitive | Tune threshold; use composite; add `datapoints-to-alarm` |

---

## Best Practices

- Every production pipeline needs at least: **failure alarm**, **duration/lag alarm**, and **missing data alarm**.
- Route prod alarms to **SNS → PagerDuty/Slack**; dev alarms to email only.
- Use **`TreatMissingData: breaching`** for freshness metrics; **`notBreaching`** for error counts.
- Set **`EvaluationPeriods >= 2`** and **`DatapointsToAlarm >= 2`** to reduce flapping.
- Name alarms consistently: `<service>-<resource>-<condition>-<env>`.
- Manage alarms via **Terraform** (`aws_cloudwatch_metric_alarm`) — treat CLI as break-glass.
- **Disable alarm actions** during planned maintenance; re-enable in deploy script `finally` block.
- Document **runbooks** linked in alarm descriptions (`Runbook: https://...`).
- Review alarm history monthly; delete unused alarms and tune thresholds based on baseline data.
