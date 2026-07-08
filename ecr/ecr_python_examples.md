# ECR — Python Boto3 Examples

## Service Overview

Boto3 ECR client for automating repository provisioning, lifecycle policies, image cleanup, and vulnerability scan gates in data platform CI/CD pipelines.

---

## AWS CLI Commands

### Quick Reference — Get Docker Login Token

```bash
aws ecr get-login-password --region us-east-1
```

Use the output with `docker login` before programmatic push workflows triggered from CI.

---

## Advanced Commands

### Export Repository URIs for Deployment Templates

```bash
aws ecr describe-repositories \
  --query 'repositories[?starts_with(repositoryName, `data-platform/`)].repositoryUri' \
  --output text
```

---

## Python (Boto3) Examples

### Production-Ready — Create Repository with Scanning and Lifecycle

```python
import json
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
ecr = boto3.client("ecr")

LIFECYCLE_POLICY = {
    "rules": [
        {
            "rulePriority": 1,
            "description": "Expire untagged images after 7 days",
            "selection": {
                "tagStatus": "untagged",
                "countType": "sinceImagePushed",
                "countUnit": "days",
                "countNumber": 7,
            },
            "action": {"type": "expire"},
        },
        {
            "rulePriority": 2,
            "description": "Keep last 15 production tags",
            "selection": {
                "tagStatus": "tagged",
                "tagPrefixList": ["prod-"],
                "countType": "imageCountMoreThan",
                "countNumber": 15,
            },
            "action": {"type": "expire"},
        },
    ]
}


def ensure_repository(name: str, scan_on_push: bool = True) -> str:
    try:
        resp = ecr.describe_repositories(repositoryNames=[name])
        uri = resp["repositories"][0]["repositoryUri"]
        logger.info("Repository exists: %s", uri)
        return uri
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "RepositoryNotFoundException":
            raise

    resp = ecr.create_repository(
        repositoryName=name,
        imageScanningConfiguration={"scanOnPush": scan_on_push},
        encryptionConfiguration={"encryptionType": "AES256"},
        tags=[{"Key": "ManagedBy", "Value": "boto3"}],
    )
    uri = resp["repository"]["repositoryUri"]
    ecr.put_lifecycle_policy(
        repositoryName=name,
        lifecyclePolicyText=json.dumps(LIFECYCLE_POLICY),
    )
    logger.info("Created repository: %s", uri)
    return uri
```

---

### Get Authorization Token for Docker Push in CI

```python
import base64
import subprocess

import boto3


def docker_login_ecr(region: str, registry_id: str) -> None:
    ecr = boto3.client("ecr", region_name=region)
    token = ecr.get_authorization_token()["authorizationData"][0]
    password = base64.b64decode(token["authorizationToken"]).split(b":")[1]
    endpoint = token["proxyEndpoint"].replace("https://", "")

    subprocess.run(
        ["docker", "login", "--username", "AWS", "--password-stdin", endpoint],
        input=password,
        check=True,
    )
    print(f"Logged in to {registry_id}.dkr.ecr.{region}.amazonaws.com")
```

---

### Delete Stale Untagged Images (Cost Cleanup)

```python
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
ecr = boto3.client("ecr")


def delete_untagged_images(repo_name: str, dry_run: bool = True) -> int:
    paginator = ecr.get_paginator("list_images")
    untagged = []
    for page in paginator.paginate(
        repositoryName=repo_name,
        filter={"tagStatus": "UNTAGGED"},
    ):
        untagged.extend(page["imageIds"])

    if not untagged:
        return 0

    if dry_run:
        logger.info("Would delete %d untagged images from %s", len(untagged), repo_name)
        return len(untagged)

    for i in range(0, len(untagged), 100):
        batch = untagged[i : i + 100]
        ecr.batch_delete_image(repositoryName=repo_name, imageIds=batch)
    logger.info("Deleted %d untagged images from %s", len(untagged), repo_name)
    return len(untagged)
```

---

### Gate Deploy on Image Scan Results

```python
import time

import boto3
from botocore.exceptions import ClientError


def wait_for_scan_and_check(
    repo_name: str,
    tag: str,
    max_critical: int = 0,
    timeout_sec: int = 300,
) -> bool:
    ecr = boto3.client("ecr")
    ecr.start_image_scan(repositoryName=repo_name, imageId={"imageTag": tag})

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            resp = ecr.describe_image_scan_findings(
                repositoryName=repo_name,
                imageId={"imageTag": tag},
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ScanNotFoundException":
                time.sleep(5)
                continue
            raise

        status = resp["imageScanStatus"]["status"]
        if status == "FAILED":
            raise RuntimeError(f"Scan failed for {repo_name}:{tag}")
        if status == "COMPLETE":
            counts = resp.get("imageScanFindings", {}).get("findingSeverityCounts", {})
            critical = counts.get("CRITICAL", 0)
            if critical > max_critical:
                raise RuntimeError(
                    f"Image {repo_name}:{tag} has {critical} CRITICAL findings "
                    f"(max allowed: {max_critical})"
                )
            return True
        time.sleep(5)

    raise TimeoutError(f"Scan did not complete within {timeout_sec}s")
```

---

### Paginate All Images Across Repositories

```python
import boto3


def inventory_all_images(prefix: str = "data-platform/") -> list[dict]:
    ecr = boto3.client("ecr")
    inventory = []
    repos = ecr.describe_repositories()["repositories"]
    for repo in repos:
        name = repo["repositoryName"]
        if not name.startswith(prefix):
            continue
        paginator = ecr.get_paginator("describe_images")
        for page in paginator.paginate(repositoryName=name):
            for detail in page["imageDetails"]:
                inventory.append({
                    "repository": name,
                    "tags": detail.get("imageTags", []),
                    "pushed_at": detail.get("imagePushedAt"),
                    "size_mb": round(detail.get("imageSizeInBytes", 0) / 1_048_576, 2),
                })
    return inventory
```

---

## Security Considerations

- Never embed ECR tokens in code; use **IAM roles** on CI runners and **IRSA** on EKS.
- Validate image digests in deployment manifests rather than mutable `:latest` tags.
- Restrict `ecr:DeleteRepository` and `ecr:BatchDeleteImage` to automation roles only.
- Enable **PrivateLink** endpoints so workers in private subnets pull without NAT.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `RepositoryAlreadyExistsException` | Idempotent create conflict | Use describe-then-create pattern |
| `LifecyclePolicyNotFoundException` | No policy attached | Call `put_lifecycle_policy` after create |
| `ScanNotFoundException` | Scan still initializing | Poll `describe_image_scan_findings` with backoff |
| `LimitExceededException` | Batch delete > 100 images | Chunk deletes into batches of 100 |

---

## Best Practices

- Wrap ECR operations in **idempotent** `ensure_*` helpers for Terraform/CDK companions.
- Log repository URI and digest on every deploy for traceability.
- Run **untagged image cleanup** on a nightly EventBridge schedule.
- Use **resource tags** (`Team`, `Environment`, `Pipeline`) for cost allocation reports.
