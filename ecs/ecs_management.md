# ECS — Container Orchestration Management

## Service Overview

**Amazon Elastic Container Service (ECS)** runs and scales containerized applications on AWS-managed infrastructure (Fargate) or EC2 capacity. Data engineers use ECS to run batch ETL containers, dbt jobs, Spark driver/executor sidecars, file processors, and long-running streaming tasks without managing Kubernetes.

**Common use cases:**
- Run scheduled Fargate tasks for nightly Parquet conversion jobs
- Execute parallel batch workers that read from SQS and write to S3
- Host Airflow task runners or custom pipeline microservices
- Run one-off data quality checks triggered by EventBridge

**When to use it:** Containerized workloads that need AWS-native orchestration with simpler ops than EKS — especially Fargate for serverless containers with per-task billing.

**Required IAM permissions (examples):** `ecs:CreateCluster`, `ecs:RegisterTaskDefinition`, `ecs:RunTask`, `ecs:DescribeTasks`, `ecs:ListTasks`, `iam:PassRole` (for task/execution roles)

---

## AWS CLI Commands

### Create Cluster

**Purpose:** Logical grouping for Fargate or EC2-backed pipeline tasks.

**Command:**

```bash
aws ecs create-cluster \
  --cluster-name data-pipeline-prod \
  --capacity-providers FARGATE FARGATE_SPOT \
  --default-capacity-provider-strategy \
    capacityProvider=FARGATE,weight=1 \
    capacityProvider=FARGATE_SPOT,weight=4 \
  --tags key=Team,value=DataEng
```

**Example Output:**

```json
{
    "cluster": {
        "clusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/data-pipeline-prod",
        "clusterName": "data-pipeline-prod",
        "status": "ACTIVE"
    }
}
```

---

### Register Task Definition (Fargate ETL Job)

**Purpose:** Define container image, CPU/memory, env vars, and IAM roles for a pipeline task.

**Command:**

```bash
aws ecs register-task-definition \
  --family spark-etl-batch \
  --network-mode awsvpc \
  --requires-compatibilities FARGATE \
  --cpu 4096 \
  --memory 8192 \
  --execution-role-arn arn:aws:iam::123456789012:role/ecsTaskExecutionRole \
  --task-role-arn arn:aws:iam::123456789012:role/SparkETLTaskRole \
  --container-definitions '[{
    "name": "spark-etl",
    "image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/data-platform/spark-etl:2025-03-01",
    "essential": true,
    "environment": [
      {"name": "INPUT_PATH", "value": "s3://raw-bucket/events/"},
      {"name": "OUTPUT_PATH", "value": "s3://curated-bucket/events/"}
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/spark-etl",
        "awslogs-region": "us-east-1",
        "awslogs-stream-prefix": "batch"
      }
    }
  }]'
```

---

### Run One-Off Task

**Purpose:** Execute a batch ETL container on demand.

**Command:**

```bash
aws ecs run-task \
  --cluster data-pipeline-prod \
  --task-definition spark-etl-batch:3 \
  --launch-type FARGATE \
  --network-configuration 'awsvpcConfiguration={
    subnets=[subnet-0abc123],
    securityGroups=[sg-0def456],
    assignPublicIp=DISABLED
  }' \
  --overrides '{
    "containerOverrides": [{
      "name": "spark-etl",
      "environment": [{"name": "RUN_DATE", "value": "2025-03-01"}]
    }]
  }'
```

---

### List Running Tasks

**Purpose:** Monitor active pipeline jobs.

**Command:**

```bash
aws ecs list-tasks \
  --cluster data-pipeline-prod \
  --desired-status RUNNING \
  --query 'taskArns' \
  --output table
```

---

### Describe Task Status and Exit Code

**Purpose:** Verify job completion and debug failures.

**Command:**

```bash
aws ecs describe-tasks \
  --cluster data-pipeline-prod \
  --tasks arn:aws:ecs:us-east-1:123456789012:task/data-pipeline-prod/abc123 \
  --query 'tasks[0].{LastStatus:lastStatus,StoppedReason:stoppedReason,ExitCode:containers[0].exitCode}'
```

**Example Output:**

```json
{
    "LastStatus": "STOPPED",
    "StoppedReason": "Essential container in task exited",
    "ExitCode": 0
}
```

---

### Create Scheduled Task (EventBridge Rule)

**Purpose:** Run nightly ETL on a cron schedule.

**Command:**

```bash
aws events put-rule \
  --name nightly-spark-etl \
  --schedule-expression "cron(0 2 * * ? *)" \
  --state ENABLED

aws events put-targets \
  --rule nightly-spark-etl \
  --targets '[{
    "Id": "spark-etl-target",
    "Arn": "arn:aws:ecs:us-east-1:123456789012:cluster/data-pipeline-prod",
    "RoleArn": "arn:aws:iam::123456789012:role/ecsEventsRole",
    "EcsParameters": {
      "TaskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/spark-etl-batch:3",
      "LaunchType": "FARGATE",
      "NetworkConfiguration": {
        "awsvpcConfiguration": {
          "Subnets": ["subnet-0abc123"],
          "SecurityGroups": ["sg-0def456"],
          "AssignPublicIp": "DISABLED"
        }
      }
    }
  }]'
```

---

## Advanced Commands

### Service Auto Scaling (SQS Backlog)

**Purpose:** Scale consumer tasks based on queue depth for decoupled ETL stages.

**Command:**

```bash
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/data-pipeline-prod/sqs-consumer \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 1 \
  --max-capacity 20

aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --resource-id service/data-pipeline-prod/sqs-consumer \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-name sqs-backlog-scaling \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 100.0,
    "CustomizedMetricSpecification": {
      "MetricName": "ApproximateNumberOfMessagesVisible",
      "Namespace": "AWS/SQS",
      "Dimensions": [{"Name": "QueueName", "Value": "etl-work-queue"}],
      "Statistic": "Average"
    },
    "ScaleInCooldown": 300,
    "ScaleOutCooldown": 60
  }'
```

---

### Execute Command into Running Container (Debug)

**Purpose:** Inspect in-flight pipeline container without SSH.

**Command:**

```bash
aws ecs execute-command \
  --cluster data-pipeline-prod \
  --task arn:aws:ecs:us-east-1:123456789012:task/data-pipeline-prod/abc123 \
  --container spark-etl \
  --interactive \
  --command "/bin/bash"
```

Requires ECS Exec enabled on service/task and SSM permissions.

---

### Tag Propagation and Cost Allocation

**Command:**

```bash
aws ecs tag-resource \
  --resource-arn arn:aws:ecs:us-east-1:123456789012:task-definition/spark-etl-batch:3 \
  --tags key=CostCenter,value=Analytics key=Pipeline,value=orders-etl
```

---

## Python (Boto3) Examples

### Run Fargate Task and Wait for Completion

```python
import boto3

ecs = boto3.client("ecs")

def run_etl_task(cluster: str, task_def: str, subnet: str, sg: str, run_date: str) -> str:
    resp = ecs.run_task(
        cluster=cluster,
        taskDefinition=task_def,
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": [subnet],
                "securityGroups": [sg],
                "assignPublicIp": "DISABLED",
            }
        },
        overrides={
            "containerOverrides": [{
                "name": "spark-etl",
                "environment": [{"name": "RUN_DATE", "value": run_date}],
            }]
        },
    )
    return resp["tasks"][0]["taskArn"]
```

---

## Security Considerations

- Separate **task execution role** (pull images, write logs) from **task role** (S3/Glue access).
- Run tasks in **private subnets** with VPC endpoints for ECR, S3, CloudWatch Logs.
- Enable **ECS Exec** only when needed; audit via CloudTrail.
- Use **secrets** from Secrets Manager/SSM Parameter Store — never plain-text env vars for credentials.
- Apply **security groups** with least-privilege egress (S3 gateway endpoint, no open outbound).

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `CannotPullContainerError` | ECR auth or missing image | Verify execution role ECR permissions and image tag |
| `ResourceInitializationError` | Logs or secrets unreachable | Check CloudWatch log group exists; verify VPC endpoints |
| Task stuck in `PENDING` | Insufficient Fargate capacity or subnet IP exhaustion | Retry; expand subnet CIDR or use alternate AZ |
| Exit code 137 | OOM killed | Increase task memory or optimize Spark/container heap |
| `AccessDeniedException` on RunTask | Missing `iam:PassRole` | Allow PassRole for task and execution roles |

---

## Best Practices

- Use **Fargate Spot** for fault-tolerant batch workloads (up to 70% savings).
- Pin **task definition revisions** in Step Functions or EventBridge targets.
- Send logs to **CloudWatch** with structured JSON for correlation with job IDs.
- Set **stopTimeout** and graceful shutdown handlers for long-running Spark jobs.
- Use **placement constraints** on EC2-backed clusters to isolate GPU/memory workloads.
- Monitor **TaskCount**, CPU, and memory via Container Insights dashboards.
