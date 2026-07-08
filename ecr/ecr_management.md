# ECR — Container Registry Management

## Service Overview

**Amazon Elastic Container Registry (ECR)** is a fully managed Docker container registry for storing, managing, and deploying container images. Data engineering teams use ECR to host custom images for Spark jobs, Airflow workers, dbt runners, Flink tasks, and Glue-adjacent container workloads on ECS, EKS, and EMR on EKS.

**Common use cases:**
- Store versioned Spark/Flink/Airflow container images for repeatable ETL
- Push CI/CD-built images from GitHub Actions, CodePipeline, or Jenkins
- Share base images across teams with lifecycle policies to control storage cost
- Scan images for vulnerabilities before deploying to production clusters

**When to use it:** Any containerized data pipeline on ECS, EKS, Fargate, or self-managed Kubernetes that needs private, IAM-integrated image storage in the same AWS account/region as compute.

**Required IAM permissions (examples):** `ecr:CreateRepository`, `ecr:DescribeRepositories`, `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`, `ecr:PutImage`, `ecr:BatchGetImage`

---

## AWS CLI Commands

### Get Login Credentials for Docker

**Purpose:** Authenticate Docker CLI to push/pull images from ECR.

**Command:**

```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com
```

**Example Output:**

```
Login Succeeded
```

**Explanation:** Returns a short-lived token (12 hours). Use the account ID and region from `aws sts get-caller-identity` and your target region.

---

### Create Repository

**Purpose:** Create a private repository for pipeline container images.

**Command:**

```bash
aws ecr create-repository \
  --repository-name data-platform/spark-etl \
  --image-scanning-configuration scanOnPush=true \
  --encryption-configuration encryptionType=AES256 \
  --tags Key=Team,Value=DataEng Key=Environment,Value=prod
```

**Example Output:**

```json
{
    "repository": {
        "repositoryArn": "arn:aws:ecr:us-east-1:123456789012:repository/data-platform/spark-etl",
        "registryId": "123456789012",
        "repositoryName": "data-platform/spark-etl",
        "repositoryUri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/data-platform/spark-etl",
        "createdAt": "2025-03-01T10:00:00+00:00",
        "imageScanningConfiguration": { "scanOnPush": true }
    }
}
```

---

### List Repositories

**Purpose:** Discover existing registries and URIs for deployment manifests.

**Command:**

```bash
aws ecr describe-repositories \
  --query 'repositories[].{Name:repositoryName,URI:repositoryUri,Created:createdAt}' \
  --output table
```

---

### Tag, Build, and Push Image

**Purpose:** Publish a new pipeline image version after CI build.

**Command:**

```bash
# Build locally
docker build -t spark-etl:2025-03-01 .

# Tag for ECR
docker tag spark-etl:2025-03-01 \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/data-platform/spark-etl:2025-03-01

# Push
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/data-platform/spark-etl:2025-03-01
```

---

### List Image Tags

**Purpose:** Audit deployed image versions and identify stale tags.

**Command:**

```bash
aws ecr list-images \
  --repository-name data-platform/spark-etl \
  --filter tagStatus=TAGGED \
  --query 'imageIds[].imageTag' \
  --output table
```

---

### Delete Untagged Images

**Purpose:** Reclaim storage from failed or intermediate CI pushes.

**Command:**

```bash
aws ecr batch-delete-image \
  --repository-name data-platform/spark-etl \
  --image-ids "$(aws ecr list-images \
    --repository-name data-platform/spark-etl \
    --filter tagStatus=UNTAGGED \
    --query 'imageIds[*]' \
    --output json)"
```

---

## Advanced Commands

### Set Lifecycle Policy (Keep Last N Tags)

**Purpose:** Automatically expire old images to control ECR storage costs.

**Command:**

```bash
aws ecr put-lifecycle-policy \
  --repository-name data-platform/spark-etl \
  --lifecycle-policy-text '{
    "rules": [{
      "rulePriority": 1,
      "description": "Keep last 10 tagged images",
      "selection": {
        "tagStatus": "tagged",
        "tagPrefixList": ["v", "202"],
        "countType": "imageCountMoreThan",
        "countNumber": 10
      },
      "action": { "type": "expire" }
    }]
  }'
```

---

### Cross-Account Repository Policy

**Purpose:** Allow a central data platform account to pull images from a shared registry.

**Command:**

```bash
aws ecr set-repository-policy \
  --repository-name data-platform/spark-etl \
  --policy-text '{
    "Version": "2012-10-17",
    "Statement": [{
      "Sid": "AllowCrossAccountPull",
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::987654321098:root" },
      "Action": [
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchCheckLayerAvailability"
      ]
    }]
  }'
```

---

### Start Image Scan and Review Findings

**Purpose:** Trigger vulnerability scan for compliance gates before deploy.

**Command:**

```bash
aws ecr start-image-scan \
  --repository-name data-platform/spark-etl \
  --image-id imageTag=2025-03-01

aws ecr describe-image-scan-findings \
  --repository-name data-platform/spark-etl \
  --image-id imageTag=2025-03-01 \
  --query 'imageScanFindings.findingSeverityCounts'
```

---

### Replicate Images to DR Region

**Purpose:** Configure ECR replication for disaster recovery of critical pipeline images.

**Command:**

```bash
aws ecr put-replication-configuration \
  --replication-configuration '{
    "rules": [{
      "destinations": [{
        "region": "us-west-2",
        "registryId": "123456789012"
      }],
      "repositoryFilters": [{
        "filter": "data-platform/",
        "filterType": "PREFIX_MATCH"
      }]
    }]
  }'
```

---

## Python (Boto3) Examples

### List Repositories and Image Counts

```python
import boto3

ecr = boto3.client("ecr")

def list_repos_with_counts() -> list[dict]:
    repos = ecr.describe_repositories()["repositories"]
    result = []
    for repo in repos:
        name = repo["repositoryName"]
        images = ecr.list_images(repositoryName=name, maxResults=1)
        result.append({"name": name, "uri": repo["repositoryUri"]})
    return result
```

---

## Security Considerations

- Enable **scan on push** and block deploys when critical CVEs are found.
- Use **AES256** or **KMS encryption** for images at rest; prefer KMS for audit trails.
- Grant **least privilege**: separate push (CI role) and pull (ECS/EKS task role) permissions.
- Avoid public repositories; use **private ECR** with VPC endpoints for air-gapped subnets.
- Rotate CI credentials; prefer **OIDC federation** over long-lived access keys for image push.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `no basic auth credentials` | Docker not logged in to ECR | Run `aws ecr get-login-password` and `docker login` |
| `RepositoryNotFoundException` | Wrong region or repo name | Verify region and exact repository name |
| `AccessDeniedException` on push | Missing `ecr:PutImage` | Update IAM policy for CI role |
| `ImagePullBackOff` in ECS/EKS | Task role lacks pull permissions | Add `ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer` to task execution role |
| `Layers already exist` / push hangs | Network or proxy issues | Check VPC endpoints for `ecr.api` and `ecr.dkr` |

---

## Best Practices

- Tag images with **git SHA**, **semver**, and **build date** (`v1.4.2-abc123f-20250301`).
- Use **lifecycle policies** to expire untagged layers and keep only recent production tags.
- Maintain a **golden base image** (JRE, Python, Spark libs) rebuilt on a schedule.
- Pin image digests in ECS task definitions and EKS manifests for immutable deploys.
- Replicate critical images to a **DR region**; document rollback tags in runbooks.
- Monitor **ECR storage metrics** in CloudWatch; large layer caches add up quickly.
