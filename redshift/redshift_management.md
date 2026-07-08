# Redshift — Cluster Management

## Service Overview

**Amazon Redshift** is a fully managed, petabyte-scale cloud data warehouse optimized for analytic queries on structured and semi-structured data. It integrates with the AWS data ecosystem for ETL, querying, and BI workloads.

**Common use cases:**
- Enterprise data warehouse for BI dashboards (QuickSight, Tableau)
- Aggregation layer fed by S3 data lake via COPY or Spectrum
- Incremental loads from operational databases (CDC → S3 → Redshift)
- Feature mart and experiment analysis for data science teams

**When to use it:** When you need complex SQL joins, window functions, and columnar storage at scale with predictable query performance — especially alongside S3-based lakes via Redshift Spectrum.

**Cluster types:**
| Type | Description |
|------|-------------|
| **Provisioned** | RA3 nodes with managed storage; resize clusters |
| **Serverless** | Auto-scaling workgroups; pay per RPU-hour |
| **Serverless vs provisioned** | Serverless for variable workloads; provisioned for steady high throughput |

---

## AWS CLI Commands

### Describe Clusters

**Purpose:** List provisioned clusters, status, and endpoints.

**Command:**

```bash
aws redshift describe-clusters \
  --query 'Clusters[].{ID:ClusterIdentifier,Status:ClusterStatus,NodeType:NodeType,Nodes:NumberOfNodes,Endpoint:Endpoint.Address}' \
  --output table
```

**Example Output:**

```
-----------------------------------------------------------------
|                      DescribeClusters                         |
+----------+---------------------------+--------+-------+-------+
| Endpoint |            ID             | Nodes  | NodeType | Status |
+----------+---------------------------+--------+-------+-------+
|  analytics-dw.abc123.us-east-1.redshift.amazonaws.com | analytics-dw |  2  | ra3.xlplus | available |
+----------+---------------------------+--------+-------+-------+
```

---

### Create Cluster

**Purpose:** Provision a new data warehouse cluster.

**Command:**

```bash
aws redshift create-cluster \
  --cluster-identifier analytics-dw \
  --node-type ra3.xlplus \
  --number-of-nodes 2 \
  --master-username admin \
  --master-user-password 'CHANGE_ME' \
  --db-name analytics \
  --vpc-security-group-ids sg-0abc123 \
  --cluster-subnet-group-name data-platform-redshift-subnet \
  --publicly-accessible false \
  --encrypted \
  --kms-key-id alias/redshift-analytics-key \
  --enhanced-vpc-routing \
  --iam-roles arn:aws:iam::123456789012:role/RedshiftSpectrumRole \
  --tags Key=Environment,Value=prod Key=Team,Value=data-platform
```

**Required IAM:** `redshift:CreateCluster` plus EC2/VPC permissions for subnet groups.

---

### Modify Cluster

**Purpose:** Resize nodes, change maintenance windows, or attach IAM roles.

**Command:**

```bash
aws redshift modify-cluster \
  --cluster-identifier analytics-dw \
  --node-type ra3.4xlarge \
  --number-of-nodes 4 \
  --iam-roles arn:aws:iam::123456789012:role/RedshiftSpectrumRole \
  --apply-immediately
```

---

### Pause and Resume Cluster (Cost Savings)

**Purpose:** Pause dev/test clusters during off-hours.

**Command:**

```bash
aws redshift pause-cluster --cluster-identifier analytics-dw-dev

aws redshift resume-cluster --cluster-identifier analytics-dw-dev
```

---

### Reboot Cluster

**Purpose:** Apply pending parameter changes or recover from node issues.

**Command:**

```bash
aws redshift reboot-cluster --cluster-identifier analytics-dw
```

---

### Delete Cluster (with Final Snapshot)

**Purpose:** Decommission cluster while retaining backup.

**Command:**

```bash
aws redshift delete-cluster \
  --cluster-identifier analytics-dw-dev \
  --final-cluster-snapshot-identifier analytics-dw-dev-final-20250301 \
  --skip-final-cluster-snapshot false
```

---

### Create Snapshot

**Purpose:** Manual backup before schema migration or major load.

**Command:**

```bash
aws redshift create-cluster-snapshot \
  --cluster-identifier analytics-dw \
  --snapshot-identifier analytics-dw-pre-migration-20250301
```

---

### Restore from Snapshot

**Purpose:** Clone cluster or recover from backup.

**Command:**

```bash
aws redshift restore-from-cluster-snapshot \
  --cluster-identifier analytics-dw-restored \
  --snapshot-identifier analytics-dw-pre-migration-20250301 \
  --node-type ra3.xlplus \
  --number-of-nodes 2
```

---

### Describe Serverless Workgroups

**Purpose:** Manage Redshift Serverless namespaces and workgroups.

**Command:**

```bash
aws redshift-serverless list-workgroups --output table

aws redshift-serverless get-workgroup --workgroup-name analytics-serverless
```

---

### Create Serverless Namespace and Workgroup

**Command:**

```bash
aws redshift-serverless create-namespace \
  --namespace-name analytics-ns \
  --admin-username admin \
  --admin-user-password 'CHANGE_ME' \
  --db-name analytics \
  --kms-key-id alias/redshift-analytics-key

aws redshift-serverless create-workgroup \
  --workgroup-name analytics-serverless \
  --namespace-name analytics-ns \
  --base-capacity 32 \
  --subnet-ids subnet-0abc123 subnet-0def456 \
  --security-group-ids sg-0abc123 \
  --publicly-accessible false
```

---

### Parameter Groups

**Purpose:** Tune query behavior (e.g., `enable_user_activity_logging`).

**Command:**

```bash
aws redshift create-cluster-parameter-group \
  --parameter-group-name analytics-custom-params \
  --parameter-group-family redshift-1.0 \
  --description "Custom params for analytics DW"

aws redshift modify-cluster-parameter-group \
  --parameter-group-name analytics-custom-params \
  --parameters ParameterName=enable_user_activity_logging,ParameterValue=true,ApplyMethod=immediate

aws redshift modify-cluster \
  --cluster-identifier analytics-dw \
  --cluster-parameter-group-name analytics-custom-params
```

---

## Advanced Commands

### Wait for Cluster Available

```bash
aws redshift wait cluster-available --cluster-identifier analytics-dw
```

### Enable Audit Logging to S3

```bash
aws redshift enable-logging \
  --cluster-identifier analytics-dw \
  --bucket-name redshift-audit-logs \
  --s3-key-prefix audit/analytics-dw/
```

### Rotate Encryption Keys

```bash
aws redshift rotate-encryption-key \
  --cluster-identifier analytics-dw \
  --new-kms-key-id alias/redshift-analytics-key-v2
```

### Cross-Region Snapshot Copy

```bash
aws redshift copy-cluster-snapshot \
  --source-cluster-identifier analytics-dw \
  --source-snapshot-identifier analytics-dw-daily-20250301 \
  --target-cluster-identifier analytics-dw-dr \
  --target-region us-west-2
```

### Filter Snapshots with JMESPath

```bash
aws redshift describe-cluster-snapshots \
  --cluster-identifier analytics-dw \
  --query 'Snapshots[?Status==`available`].{ID:SnapshotIdentifier,Start:SnapshotCreateTime,Size:TotalBackupSizeInMegaBytes}' \
  --output table
```

### Scheduled Actions (Pause/Resume Automation)

```bash
aws redshift create-scheduled-action \
  --scheduled-action-name pause-analytics-dev-nights \
  --schedule "cron(0 22 * * ? *)" \
  --iam-role arn:aws:iam::123456789012:role/RedshiftSchedulerRole \
  --target-action '{"PauseCluster":{"ClusterIdentifier":"analytics-dw-dev"}}'
```

---

## Python (Boto3) Examples

### Basic — Wait for Cluster

```python
import boto3

client = boto3.client("redshift")
waiter = client.get_waiter("cluster_available")
waiter.wait(ClusterIdentifier="analytics-dw")
print("Cluster is available")
```

### Production-Ready — Create Snapshot with Polling

```python
import logging
import time

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def create_snapshot(cluster_id: str, snapshot_id: str, timeout_sec: int = 3600) -> None:
    client = boto3.client("redshift")
    try:
        client.create_cluster_snapshot(
            ClusterIdentifier=cluster_id,
            SnapshotIdentifier=snapshot_id,
        )
    except ClientError as exc:
        logger.error("Snapshot creation failed: %s", exc.response["Error"]["Message"])
        raise

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        resp = client.describe_cluster_snapshots(SnapshotIdentifier=snapshot_id)
        status = resp["Snapshots"][0]["Status"]
        if status == "available":
            logger.info("Snapshot %s is available", snapshot_id)
            return
        if status == "failed":
            raise RuntimeError(f"Snapshot {snapshot_id} failed")
        time.sleep(30)
    raise TimeoutError(f"Snapshot {snapshot_id} not available within {timeout_sec}s")
```

See [redshift_python_examples.md](redshift_python_examples.md) for Data API and serverless patterns.

---

## Security Considerations

- Enable **encryption at rest** with a customer-managed **KMS key**.
- Set **`publicly-accessible false`**; access via VPN, Direct Connect, or bastion in private subnet.
- Use **security groups** allowing only BI tools and ETL hosts on port 5439.
- Attach **IAM roles** for COPY/UNLOAD/Spectrum — never embed long-lived keys in SQL.
- Enable **audit logging** to S3 and **Database Activity Streams** for compliance.
- Rotate master credentials via **Secrets Manager** integration.
- Apply **column-level security** and **row-level security** for multi-tenant marts.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `ClusterNotFound` | Wrong region or deleted cluster | Verify `--region` and cluster identifier |
| `InsufficientCapacity` | AZ capacity shortage | Retry different AZ/node type or use Serverless |
| Cluster stuck `modifying` | Resize in progress | Wait; check Events tab / `describe-events` |
| Cannot connect (timeout) | SG or routing issue | Verify SG inbound 5439; check route tables and NACLs |
| `SnapshotAlreadyExists` | Duplicate snapshot ID | Use timestamped snapshot identifiers |
| High storage on RA3 | Unvacuumed tables | Run `VACUUM` and `ANALYZE`; check `stv_tbl_perm` |

---

## Best Practices

- Use **RA3 nodes** with managed storage for decoupled compute/storage scaling.
- **Pause** non-prod clusters on a schedule to reduce cost.
- Take **automated snapshots** (1–35 day retention) and copy critical snapshots cross-region for DR.
- Attach a dedicated **Spectrum IAM role** at cluster creation for S3 external tables.
- Use **Enhanced VPC Routing** so COPY/UNLOAD traffic stays on AWS network.
- Tag clusters for cost allocation (`Environment`, `CostCenter`, `Workload`).
- Monitor **CPUUtilization**, **PercentageDiskSpaceUsed**, and **HealthStatus** in CloudWatch.
- Prefer **Redshift Serverless** for ad-hoc/analytics with variable concurrency.
