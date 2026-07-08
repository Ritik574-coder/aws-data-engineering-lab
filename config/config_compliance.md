# AWS Config — Compliance Monitoring

## Service Overview

**AWS Config** continuously records AWS resource configurations and evaluates them against rules for compliance. It provides configuration history, change notifications, and remediation via SSM Automation or Lambda.

**Common use cases:**
- Detect S3 buckets without encryption or public access blocks
- Ensure RDS instances have backup retention ≥ 7 days
- Track IAM policy changes affecting data pipeline roles
- Auto-remediate non-compliant security group rules

**When to use it:** When you need continuous compliance auditing, configuration drift detection, or automated remediation across data platform resources.

---

## AWS CLI Commands

### Describe Configuration Recorder Status

**Purpose:** Verify Config is recording in the account/region.

**Command:**

```bash
aws configservice describe-configuration-recorder-status
```

**Example Output:**

```json
{
    "ConfigurationRecordersStatus": [
        {
            "name": "default",
            "lastStatus": "SUCCESS",
            "recording": true,
            "lastStartTime": "2025-01-01T00:00:00+00:00"
        }
    ]
}
```

---

### Put Configuration Recorder

```bash
aws configservice put-configuration-recorder \
  --configuration-recorder '{
    "name": "default",
    "roleARN": "arn:aws:iam::123456789012:role/aws-service-role/config.amazonaws.com/AWSServiceRoleForConfig",
    "recordingGroup": {
      "allSupported": true,
      "includeGlobalResourceTypes": true
    }
  }'
```

---

### Start Configuration Recorder

```bash
aws configservice start-configuration-recorder --configuration-recorder-name default
```

---

### Put Delivery Channel

**Purpose:** Deliver configuration snapshots to S3 and SNS notifications.

**Command:**

```bash
aws configservice put-delivery-channel \
  --delivery-channel '{
    "name": "default",
    "s3BucketName": "my-config-bucket-123456789012",
    "snsTopicARN": "arn:aws:sns:us-east-1:123456789012:config-compliance-alerts"
  }'
```

---

### Put Config Rule — S3 Bucket Encryption

```bash
aws configservice put-config-rule \
  --config-rule '{
    "ConfigRuleName": "s3-bucket-server-side-encryption-enabled",
    "Source": {
      "Owner": "AWS",
      "SourceIdentifier": "S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED"
    },
    "Scope": {
      "ComplianceResourceTypes": ["AWS::S3::Bucket"]
    }
  }'
```

---

### Put Managed Config Rule — RDS Backup

```bash
aws configservice put-config-rule \
  --config-rule '{
    "ConfigRuleName": "rds-backup-retention-check",
    "Source": {
      "Owner": "AWS",
      "SourceIdentifier": "DB_INSTANCE_BACKUP_ENABLED"
    }
  }'
```

---

### Get Compliance Summary

```bash
aws configservice get-compliance-summary-by-config-rule
```

**Example Output:**

```json
{
    "ComplianceSummariesByConfigRule": [
        {
            "ConfigRuleName": "s3-bucket-server-side-encryption-enabled",
            "ComplianceSummary": {
                "CompliantResourceCount": {"CappedCount": 12, "CapExceeded": false},
                "NonCompliantResourceCount": {"CappedCount": 2, "CapExceeded": false},
                "ComplianceSummaryTimestamp": "2025-03-01T12:00:00+00:00"
            }
        }
    ]
}
```

---

### Get Non-Compliant Resources

```bash
aws configservice get-compliance-details-by-config-rule \
  --config-rule-name s3-bucket-server-side-encryption-enabled \
  --compliance-types NON_COMPLIANT
```

---

### Describe Config Rule Evaluation Status

```bash
aws configservice describe-compliance-by-config-rule \
  --config-rule-names s3-bucket-server-side-encryption-enabled
```

---

### Delete Config Rule

```bash
aws configservice delete-config-rule \
  --config-rule-name s3-bucket-server-side-encryption-enabled
```

---

## Advanced Commands

### Custom Lambda Config Rule

Deploy a Lambda function that evaluates whether Glue databases have LF-Tags, then:

```bash
aws configservice put-config-rule \
  --config-rule '{
    "ConfigRuleName": "glue-database-lf-tags",
    "Source": {
      "Owner": "CUSTOM_LAMBDA",
      "SourceIdentifier": "arn:aws:lambda:us-east-1:123456789012:function:ConfigGlueLfTagCheck",
      "SourceDetails": [{
        "EventSource": "aws.config",
        "MessageType": "ConfigurationItemChangeNotification"
      }]
    }
  }'
```

### Remediation Configuration

```bash
aws configservice put-remediation-configurations \
  --remediation-configurations '[{
    "ConfigRuleName": "s3-bucket-public-read-prohibited",
    "TargetType": "SSM_DOCUMENT",
    "TargetIdentifier": "AWS-ConfigureS3BucketPublicAccessBlock",
    "TargetVersion": "1",
    "Parameters": {
      "BucketName": {"ResourceValue": {"Value": "RESOURCE_ID"}},
      "BlockPublicAcls": {"StaticValue": {"Values": ["true"]}}
    },
    "Automatic": true,
    "MaximumAutomaticAttempts": 3
  }]'
```

### Aggregate Compliance (Multi-Account)

```bash
aws configservice describe-configuration-aggregators
aws configservice get-compliance-summary-by-config-rule \
  --configuration-aggregator-name org-wide-aggregator
```

### Select Resource Config History

```bash
aws configservice get-resource-config-history \
  --resource-type AWS::S3::Bucket \
  --resource-id my-data-lake-raw \
  --limit 10
```

---

## Python Boto3 Examples

```python
import boto3

config = boto3.client("config")

# List non-compliant resources for a rule
response = config.get_compliance_details_by_config_rule(
    ConfigRuleName="s3-bucket-server-side-encryption-enabled",
    ComplianceTypes=["NON_COMPLIANT"],
)
for result in response.get("EvaluationResults", []):
    print(result["EvaluationResultIdentifier"]["EvaluationResultQualifier"]["ResourceId"])
```

---

## Security Considerations

- Config service role needs read access to all recorded resource types.
- Store configuration snapshots in an **encrypted S3 bucket** with restricted access.
- Use **AWS Config Aggregator** in a security account for org-wide visibility.
- Protect remediation roles — automatic remediation can modify production resources.
- Enable **delivery channel SNS** encryption with KMS.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| Recorder not running | Delivery channel missing | Create delivery channel before starting recorder |
| Rule `INSUFFICIENT_DATA` | New resource or rule | Wait for evaluation cycle; verify resource type in scope |
| Aggregator empty | Missing authorization | Authorize aggregator account in member accounts |
| Remediation not triggering | `Automatic: false` or missing permissions | Enable automatic remediation; check SSM document permissions |
| High API costs | Recording all resources globally | Scope recording group to required types/regions |

---

## Best Practices

- **Enable Config in all data platform accounts** — especially prod and shared services.
- **Start with AWS managed rules** for S3, RDS, IAM, and encryption before custom rules.
- **Use conformance packs** — deploy pre-built rule sets for CIS or PCI benchmarks.
- **Integrate with Security Hub** for centralized findings dashboard.
- **Set up SNS alerts** for `NON_COMPLIANT` transitions on critical rules.
- **Review remediation carefully** — test in non-prod before enabling automatic fixes.
- **Retain config history** in S3 with lifecycle policies aligned to compliance requirements.
