# EMR — Python Boto3 Examples

## Service Overview

Boto3 EMR and EMR Serverless clients for automating cluster provisioning, step submission, cost-aware transient jobs, and pipeline integration in data engineering platforms.

---

## AWS CLI Commands

### Quick Reference — Terminate Cluster

```bash
aws emr terminate-clusters --cluster-ids j-ABCDEFGHIJK1
```

---

## Advanced Commands

### Get Step Failure Details

```bash
aws emr list-steps --cluster-id j-ABCDEFGHIJK1 \
  --query 'Steps[?Status.State==`FAILED`].{Name:Name,Reason:Status.FailureDetails.Reason,Log:Status.FailureDetails.LogFile}'
```

---

## Python (Boto3) Examples

### Production-Ready — Launch Transient Spark Cluster

```python
import logging
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
emr = boto3.client("emr")


def run_transient_spark_etl(
    cluster_name: str,
    release_label: str,
    script_s3_uri: str,
    input_path: str,
    output_path: str,
    log_uri: str,
    subnet_id: str,
    service_role: str,
    instance_profile: str,
    master_sg: str,
    slave_sg: str,
) -> str:
    steps = [{
        "Name": "Spark ETL",
        "ActionOnFailure": "TERMINATE_CLUSTER",
        "HadoopJarStep": {
            "Jar": "command-runner.jar",
            "Args": [
                "spark-submit",
                "--deploy-mode", "cluster",
                script_s3_uri,
                "--input", input_path,
                "--output", output_path,
            ],
        },
    }]

    try:
        resp = emr.run_job_flow(
            Name=f"{cluster_name}-{datetime.now(timezone.utc):%Y%m%d%H%M}",
            ReleaseLabel=release_label,
            Applications=[{"Name": "Spark"}, {"Name": "Hadoop"}],
            LogUri=log_uri,
            Instances={
                "InstanceGroups": [
                    {
                        "Name": "Master",
                        "Market": "ON_DEMAND",
                        "InstanceRole": "MASTER",
                        "InstanceType": "m5.xlarge",
                        "InstanceCount": 1,
                    },
                    {
                        "Name": "Core",
                        "Market": "ON_DEMAND",
                        "InstanceRole": "CORE",
                        "InstanceType": "m5.xlarge",
                        "InstanceCount": 2,
                    },
                    {
                        "Name": "Task",
                        "Market": "SPOT",
                        "InstanceRole": "TASK",
                        "InstanceType": "m5.xlarge",
                        "InstanceCount": 4,
                        "BidPrice": "0.25",
                    },
                ],
                "Ec2SubnetId": subnet_id,
                "EmrManagedMasterSecurityGroup": master_sg,
                "EmrManagedSlaveSecurityGroup": slave_sg,
                "KeepJobFlowAliveWhenNoSteps": False,
                "TerminationProtected": False,
            },
            Steps=steps,
            VisibleToAllUsers=True,
            JobFlowRole=instance_profile,
            ServiceRole=service_role,
            Configurations=[{
                "Classification": "spark-defaults",
                "Properties": {
                    "spark.dynamicAllocation.enabled": "true",
                    "spark.sql.adaptive.enabled": "true",
                },
            }],
            Tags=[{"Key": "ManagedBy", "Value": "boto3"}],
        )
        cluster_id = resp["JobFlowId"]
        logger.info("Started EMR cluster %s", cluster_id)
        return cluster_id
    except ClientError:
        logger.exception("Failed to create EMR cluster")
        raise
```

---

### Wait for Cluster Termination

```python
import time

import boto3


def wait_for_cluster_termination(cluster_id: str, timeout_sec: int = 7200) -> None:
    emr = boto3.client("emr")
    terminal = {"TERMINATED", "TERMINATED_WITH_ERRORS", "CANCELLED"}
    deadline = time.time() + timeout_sec

    while time.time() < deadline:
        state = emr.describe_cluster(ClusterId=cluster_id)["Cluster"]["Status"]["State"]
        if state in terminal:
            if state != "TERMINATED":
                raise RuntimeError(f"Cluster {cluster_id} ended in {state}")
            return
        time.sleep(60)

    raise TimeoutError(f"Cluster {cluster_id} did not terminate within {timeout_sec}s")
```

---

### Add Spark Step to Existing Cluster

```python
import boto3


def add_spark_step(cluster_id: str, step_name: str, script_uri: str, args: list[str]) -> str:
    emr = boto3.client("emr")
    resp = emr.add_job_flow_steps(
        JobFlowId=cluster_id,
        Steps=[{
            "Name": step_name,
            "ActionOnFailure": "CONTINUE",
            "HadoopJarStep": {
                "Jar": "command-runner.jar",
                "Args": ["spark-submit", "--deploy-mode", "cluster", script_uri, *args],
            },
        }],
    )
    return resp["StepIds"][0]
```

---

### EMR Serverless Job Run

```python
import logging
import time

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def run_emr_serverless_spark(
    application_id: str,
    execution_role_arn: str,
    entry_point: str,
    entry_args: list[str],
    spark_params: str = "",
    timeout_sec: int = 3600,
) -> str:
    client = boto3.client("emr-serverless")
    try:
        resp = client.start_job_run(
            applicationId=application_id,
            executionRoleArn=execution_role_arn,
            jobDriver={
                "sparkSubmit": {
                    "entryPoint": entry_point,
                    "entryPointArguments": entry_args,
                    "sparkSubmitParameters": spark_params,
                }
            },
        )
    except ClientError:
        logger.exception("Failed to start EMR Serverless job")
        raise

    job_run_id = resp["jobRunId"]
    deadline = time.time() + timeout_sec

    while time.time() < deadline:
        run = client.get_job_run(applicationId=application_id, jobRunId=job_run_id)["jobRun"]
        state = run["state"]
        if state in ("SUCCESS",):
            logger.info("Job %s succeeded", job_run_id)
            return job_run_id
        if state in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"Job {job_run_id} ended in {state}: {run.get('stateDetails')}")
        time.sleep(15)

    client.cancel_job_run(applicationId=application_id, jobRunId=job_run_id)
    raise TimeoutError(f"Job {job_run_id} timed out after {timeout_sec}s")
```

---

### Cost Guard — Terminate Idle Clusters

```python
from datetime import datetime, timezone, timedelta

import boto3


def terminate_idle_clusters(max_idle_hours: int = 2) -> list[str]:
    emr = boto3.client("emr")
    terminated = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_idle_hours)

    clusters = emr.list_clusters(ClusterStates=["WAITING"])["Clusters"]
    for cluster in clusters:
        ready = cluster["Status"]["Timeline"].get("ReadyDateTime")
        if ready and ready < cutoff:
            cid = cluster["Id"]
            emr.terminate_job_flows(JobFlowIds=[cid])
            terminated.append(cid)
    return terminated
```

---

## Security Considerations

- Pass **execution roles** with S3 prefix-scoped policies to EMR Serverless jobs.
- Disable `VisibleToAllUsers` in multi-account environments unless required.
- Validate bootstrap script S3 URIs against an allowlist bucket prefix.
- Enable **Lake Formation** integration when accessing governed tables from Spark.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `RunJobFlow` throttled | API rate limit | Retry with exponential backoff |
| Step ID not returned | Malformed step JSON | Validate `HadoopJarStep` structure |
| Serverless `AccessDenied` | Execution role S3 deny | Check role policy and bucket policy |
| Idle termination false positive | Cluster waiting for manual steps | Filter by cluster tag or step count |

---

## Best Practices

- Wrap `run_job_flow` in **Step Functions** with retry for Spot capacity errors.
- Tag clusters with `Pipeline`, `RunDate`, and `CostCenter` for chargeback.
- Persist cluster ID and step IDs to a **metadata table** for lineage tracking.
- Use **S3 log URI** conventions: `s3://logs/emr/{pipeline}/{date}/`.
- Prefer EMR Serverless for sporadic jobs; use EC2 EMR for tight latency/control needs.
