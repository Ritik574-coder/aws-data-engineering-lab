# EMR — Cluster Management

## Service Overview

**Amazon EMR (Elastic MapReduce)** is a managed big data platform for running Apache Spark, Hive, Presto/Trino, HBase, and Flink at scale on EC2, with optional EMR on EKS for containerized Spark. It is a core service for large-scale batch ETL, log processing, feature engineering, and ML data prep.

**Common use cases:**
- Nightly Spark jobs transforming raw S3 data into curated Parquet zones
- Ad-hoc Hive/Spark SQL over petabyte-scale datasets
- Bootstrap transient clusters for cost-efficient batch (create → process → terminate)
- Long-running analytics clusters with auto-scaling task nodes

**When to use it:** Heavy distributed processing where managed Spark/Hadoop clusters are faster to operate than self-built EC2 fleets — especially for transient batch workloads with Spot task nodes.

**Required IAM permissions (examples):** `elasticmapreduce:RunJobFlow`, `elasticmapreduce:DescribeCluster`, `elasticmapreduce:TerminateJobFlows`, `iam:PassRole` (EMR service and EC2 instance roles)

---

## AWS CLI Commands

### Create Transient Spark Cluster (Batch ETL)

**Purpose:** Spin up a cluster, run a Spark step, and auto-terminate when done.

**Command:**

```bash
aws emr create-cluster \
  --name orders-etl-20250301 \
  --release-label emr-7.2.0 \
  --applications Name=Spark Name=Hadoop \
  --log-uri s3://emr-logs-bucket/logs/ \
  --service-role EMR_DefaultRole \
  --ec2-attributes '{
    "InstanceProfile": "EMR_EC2_DefaultRole",
    "EmrManagedMasterSecurityGroup": "sg-master",
    "EmrManagedSlaveSecurityGroup": "sg-core",
    "KeyName": "data-pipeline-key",
    "SubnetId": "subnet-0abc123"
  }' \
  --instance-groups '[
    {"Name":"Master","InstanceGroupType":"MASTER","InstanceType":"m5.xlarge","InstanceCount":1},
    {"Name":"Core","InstanceGroupType":"CORE","InstanceType":"m5.xlarge","InstanceCount":2,"EbsConfiguration":{"EbsBlockDeviceConfigs":[{"VolumeSpecification":{"VolumeType":"gp3","SizeInGB":256},"VolumesPerInstance":2}]}},
    {"Name":"Task","InstanceGroupType":"TASK","InstanceType":"m5.xlarge","InstanceCount":4,"BidPrice":"0.20","AutoScalingPolicy":{"Constraints":{"MinCapacity":0,"MaxCapacity":10},"Rules":[{"Name":"ScaleOut","Description":"","Action":{"SimpleScalingPolicyConfiguration":{"ScalingAdjustment":2,"CoolDown":300}},"Trigger":{"CloudWatchAlarmDefinition":{"ComparisonOperator":"GREATER_THAN","MetricName":"YARNMemoryAvailablePercentage","Namespace":"AWS/ElasticMapReduce","Period":300,"EvaluationPeriods":1,"Threshold":15,"Statistic":"AVERAGE","Unit":"PERCENT"}}}]}}
  ]' \
  --configurations '[
    {"Classification":"spark-defaults","Properties":{"spark.dynamicAllocation.enabled":"true","spark.sql.adaptive.enabled":"true"}},
    {"Classification":"yarn-site","Properties":{"yarn.nodemanager.pmem-check-enabled":"false"}}
  ]' \
  --steps '[
    {"Name":"Orders ETL","ActionOnFailure":"TERMINATE_CLUSTER","Jar":"command-runner.jar","Args":["spark-submit","--deploy-mode","cluster","s3://scripts-bucket/orders_etl.py","--input","s3://raw/orders/","--output","s3://curated/orders/dt=2025-03-01/"]}
  ]' \
  --auto-terminate \
  --tags Team=DataEng Pipeline=orders-etl
```

---

### List Clusters

**Purpose:** Monitor active and recent EMR jobs.

**Command:**

```bash
aws emr list-clusters \
  --active \
  --query 'Clusters[].{Id:Id,Name:Name,Status:Status.State,Created:Status.Timeline.CreationDateTime}' \
  --output table
```

---

### Describe Cluster

**Purpose:** Get master DNS, applications, and bootstrap actions.

**Command:**

```bash
aws emr describe-cluster \
  --cluster-id j-ABCDEFGHIJK1 \
  --query 'Cluster.{Name:Name,State:Status.State,Master:MasterPublicDnsName,Release:ReleaseLabel,Apps:Applications[].Name}'
```

**Example Output:**

```json
{
    "Name": "orders-etl-20250301",
    "State": "RUNNING",
    "Master": "ec2-1-2-3-4.compute-1.amazonaws.com",
    "Release": "emr-7.2.0",
    "Apps": ["Hadoop", "Spark"]
}
```

---

### Add Step to Running Cluster

**Purpose:** Submit additional Spark job without new cluster.

**Command:**

```bash
aws emr add-steps \
  --cluster-id j-ABCDEFGHIJK1 \
  --steps '[
    {"Name":"DQ Check","ActionOnFailure":"CONTINUE","Jar":"command-runner.jar","Args":["spark-submit","s3://scripts-bucket/dq_check.py","--table","orders"]}
  ]'
```

---

### Terminate Cluster

**Purpose:** Stop billing for completed or failed transient clusters.

**Command:**

```bash
aws emr terminate-clusters --cluster-ids j-ABCDEFGHIJK1
```

---

### SSH to Master (Troubleshooting)

**Purpose:** Inspect YARN/Spark UI and logs on persistent clusters.

**Command:**

```bash
MASTER_DNS=$(aws emr describe-cluster --cluster-id j-ABCDEFGHIJK1 \
  --query 'Cluster.MasterPublicDnsName' --output text)

ssh -i ~/.ssh/data-pipeline-key.pem hadoop@${MASTER_DNS}
# Spark history: http://${MASTER_DNS}:18080
# YARN RM:       http://${MASTER_DNS}:8088
```

---

## Advanced Commands

### Managed Scaling Policy

**Purpose:** Automatically resize core/task nodes based on YARN metrics.

**Command:**

```bash
aws emr put-managed-scaling-policy \
  --cluster-id j-ABCDEFGHIJK1 \
  --managed-scaling-policy '{
    "ComputeLimits": {
      "UnitType": "Instances",
      "MinimumCapacityUnits": 2,
      "MaximumCapacityUnits": 20,
      "MaximumOnDemandCapacityUnits": 4,
      "MaximumCoreCapacityUnits": 10
    }
  }'
```

---

### Create EMR Studio (Notebooks)

**Purpose:** Provide Jupyter-based Spark notebooks for analysts.

**Command:**

```bash
aws emr create-studio \
  --name data-analyst-studio \
  --auth-mode IAM \
  --vpc-id vpc-0abc123 \
  --subnet-ids subnet-0def456 \
  --service-role EMR_DefaultRole \
  --workspace-security-group-id sg-studio \
  --engine-security-group-id sg-engine \
  --default-s3-location s3://emr-studio-workspace/
```

---

### Serverless Spark (EMR Serverless)

**Purpose:** Run Spark without managing clusters — pay per vCPU/memory used.

**Command:**

```bash
aws emr-serverless create-application \
  --name spark-etl-serverless \
  --release-label emr-7.2.0 \
  --type SPARK \
  --initial-capacity '{
    "DRIVER": {"workerCount": 1, "workerConfiguration": {"cpu": "4 vCPU", "memory": "16 GB"}},
    "EXECUTOR": {"workerCount": 10, "workerConfiguration": {"cpu": "4 vCPU", "memory": "16 GB"}}
  }'

aws emr-serverless start-job-run \
  --application-id 00f1234567890abcd \
  --execution-role-arn arn:aws:iam::123456789012:role/EMRServerlessJobRole \
  --job-driver '{
    "sparkSubmit": {
      "entryPoint": "s3://scripts-bucket/orders_etl.py",
      "entryPointArguments": ["--date","2025-03-01"],
      "sparkSubmitParameters": "--conf spark.executor.cores=4 --conf spark.executor.memory=8g"
    }
  }'
```

---

## Python (Boto3) Examples

### List Running Clusters

```python
import boto3

emr = boto3.client("emr")

def list_active_clusters() -> list[dict]:
    resp = emr.list_clusters(ClusterStates=["RUNNING", "WAITING"])
    return [
        {"id": c["Id"], "name": c["Name"], "state": c["Status"]["State"]}
        for c in resp["Clusters"]
    ]
```

---

## Security Considerations

- Place clusters in **private subnets**; restrict master SG ingress to bastion/VPN CIDRs.
- Use **EMR roles** with least-privilege S3 prefix access for input/output buckets.
- Enable **at-rest encryption** for EBS and in-transit encryption for Spark shuffle.
- Enable **Kerberos** or IAM authentication for multi-tenant clusters when required.
- Store bootstrap scripts and Spark JARs in **versioned S3** buckets with integrity checks.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| Cluster stuck in `STARTING` | Bootstrap action failure or SG rules | Check bootstrap logs in S3 `log-uri`; verify SG egress |
| Step `FAILED` | Spark OOM or bad input path | Review step stderr in S3 logs; tune executor memory |
| `VALIDATION_ERROR` on create | Invalid instance type for release | Check EMR release compatibility matrix |
| Spot task nodes terminated | Spot interruption | Use on-demand core nodes; enable Spot diversification |
| Slow shuffle | Cross-AZ traffic or small partitions | Co-locate data and compute; increase partitions |

---

## Best Practices

- Prefer **transient clusters** with `--auto-terminate` for scheduled batch ETL.
- Use **Spot instances** for task nodes; keep master/core on-demand for stability.
- Centralize **bootstrap scripts** for Python deps, JARs, and CloudWatch agent setup.
- Write logs to a dedicated **S3 log bucket** with lifecycle policies.
- Right-size with **managed scaling** and Spark dynamic allocation.
- Consider **EMR Serverless** for variable workloads to eliminate idle cluster cost.
