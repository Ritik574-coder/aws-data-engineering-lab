# EKS — Python Boto3 Examples

## Service Overview

Boto3 EKS client for cluster lifecycle automation, add-on management, access control, and integration with data platform provisioning pipelines.

---

## AWS CLI Commands

### Quick Reference — Update kubeconfig

```bash
aws eks update-kubeconfig --name data-platform-prod --region us-east-1
```

---

## Advanced Commands

### Export Cluster CA and Endpoint for CI/CD

```bash
aws eks describe-cluster --name data-platform-prod \
  --query 'cluster.{Endpoint:endpoint,CA:certificateAuthority.data}' \
  --output json
```

---

## Python (Boto3) Examples

### Production-Ready — Wait for Cluster Active

```python
import logging
import time

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
eks = boto3.client("eks")


def wait_for_cluster_active(cluster_name: str, timeout_sec: int = 1800) -> dict:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            resp = eks.describe_cluster(name=cluster_name)
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ResourceNotFoundException":
                time.sleep(15)
                continue
            raise

        cluster = resp["cluster"]
        status = cluster["status"]
        logger.info("Cluster %s status: %s", cluster_name, status)

        if status == "ACTIVE":
            return cluster
        if status in ("FAILED", "DELETING"):
            raise RuntimeError(f"Cluster {cluster_name} entered {status}")

        time.sleep(30)

    raise TimeoutError(f"Cluster {cluster_name} not ACTIVE within {timeout_sec}s")
```

---

### Create Node Group with Tags

```python
import boto3
from botocore.exceptions import ClientError


def create_spark_nodegroup(
    cluster_name: str,
    nodegroup_name: str,
    node_role_arn: str,
    subnet_ids: list[str],
    instance_types: list[str],
    min_size: int,
    max_size: int,
    desired_size: int,
) -> str:
    eks = boto3.client("eks")
    try:
        resp = eks.create_nodegroup(
            clusterName=cluster_name,
            nodegroupName=nodegroup_name,
            nodeRole=node_role_arn,
            subnets=subnet_ids,
            scalingConfig={
                "minSize": min_size,
                "maxSize": max_size,
                "desiredSize": desired_size,
            },
            instanceTypes=instance_types,
            diskSize=200,
            labels={"workload": "spark", "managed-by": "boto3"},
            tags={"Team": "DataEng", "Workload": "spark"},
        )
        return resp["nodegroup"]["nodegroupArn"]
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ResourceInUseException":
            desc = eks.describe_nodegroup(
                clusterName=cluster_name, nodegroupName=nodegroup_name
            )
            return desc["nodegroup"]["nodegroupArn"]
        raise
```

---

### Install or Update EBS CSI Add-on

```python
import boto3


def ensure_ebs_csi_addon(cluster_name: str, service_account_role_arn: str) -> None:
    eks = boto3.client("eks")
    addons = eks.list_addons(clusterName=cluster_name).get("addons", [])

    params = {
        "clusterName": cluster_name,
        "addonName": "aws-ebs-csi-driver",
        "serviceAccountRoleArn": service_account_role_arn,
        "resolveConflicts": "OVERWRITE",
    }

    if "aws-ebs-csi-driver" in addons:
        eks.update_addon(**params)
    else:
        eks.create_addon(**params)
```

---

### Create Access Entry for Pipeline CI Role

```python
import boto3


def grant_cluster_access(cluster_name: str, principal_arn: str, policy_arn: str) -> None:
    eks = boto3.client("eks")
    try:
        eks.create_access_entry(
            clusterName=cluster_name,
            principalArn=principal_arn,
            type="STANDARD",
        )
    except eks.exceptions.ResourceInUseException:
        pass

    eks.associate_access_policy(
        clusterName=cluster_name,
        principalArn=principal_arn,
        policyArn=policy_arn,
        accessScope={"type": "cluster"},
    )
```

---

### List Clusters and Nodegroup Capacity

```python
import boto3


def cluster_capacity_report() -> list[dict]:
    eks = boto3.client("eks")
    report = []
    for cluster_name in eks.list_clusters()["clusters"]:
        nodegroups = eks.list_nodegroups(clusterName=cluster_name)["nodegroups"]
        ng_details = []
        for ng in nodegroups:
            desc = eks.describe_nodegroup(clusterName=cluster_name, nodegroupName=ng)
            scaling = desc["nodegroup"]["scalingConfig"]
            ng_details.append({
                "name": ng,
                "desired": scaling["desiredSize"],
                "min": scaling["minSize"],
                "max": scaling["maxSize"],
                "status": desc["nodegroup"]["status"],
            })
        report.append({"cluster": cluster_name, "nodegroups": ng_details})
    return report
```

---

### Generate kubeconfig Token for Automation (with awscli v2 helper pattern)

```python
import boto3


def get_bearer_token(cluster_name: str, region: str) -> str:
    """Generate EKS authentication token for Kubernetes API clients."""
    from botocore.signers import RequestSigner

    session = boto3.Session(region_name=region)
    client = session.client("sts")
    service_id = client.meta.service_model.service_id

    signer = RequestSigner(
        service_id,
        region,
        "sts",
        "v4",
        session.get_credentials(),
        session.events,
    )

    url = (
        f"https://sts.{region}.amazonaws.com/"
        f"?Action=GetCallerIdentity&Version=2011-06-15"
    )
    presigned = signer.generate_presigned_url(
        {"method": "GET", "url": url, "body": {}, "headers": {}, "context": {}},
        region_name=region,
        expires_in=60,
        operation_name="",
    )

    sts_client = boto3.client("sts", region_name=region)
    token = sts_client.generate_presigned_url(
        "get_caller_identity",
        Params={"ClusterName": cluster_name},
        ExpiresIn=60,
        HttpMethod="GET",
    )
    # For production, prefer aws eks get-token or official exec plugin
    return token
```

---

## Security Considerations

- Automate **access entry** provisioning; avoid manual aws-auth ConfigMap edits.
- Scope CI/CD roles to **namespace-level** access policies where possible.
- Audit `create_access_entry` and `associate_access_policy` via CloudTrail alerts.
- Never store kubeconfig with long-lived credentials in source control.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `ResourceInUseException` | Nodegroup already exists | Use describe and update scaling config |
| `InvalidParameterException` on subnets | Subnets in unsupported AZ | Use subnets tagged for EKS cluster |
| Add-on `CREATE_FAILED` | IAM role trust mismatch | Verify OIDC trust for CSI driver SA |
| Token generation fails in automation | Missing `sts:GetCallerIdentity` | Grant sts permissions to automation role |

---

## Best Practices

- Encapsulate cluster bootstrap in **idempotent** provisioning scripts alongside Terraform.
- Poll nodegroup status before deploying Spark Operator or Airflow Helm releases.
- Tag nodegroups with `k8s.io/cluster-autoscaler/enabled` for autoscaler discovery.
- Export cluster metadata to a **central config store** (SSM Parameter Store) for downstream tools.
