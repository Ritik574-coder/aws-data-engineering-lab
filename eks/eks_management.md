# EKS — Kubernetes Cluster Management

## Service Overview

**Amazon Elastic Kubernetes Service (EKS)** is a managed Kubernetes control plane for running containerized data platforms at scale. Teams deploy Spark on Kubernetes, Apache Flink, Airflow (KubernetesExecutor/Celery), Kafka connectors, dbt containers, and ML feature pipelines on EKS.

**Common use cases:**
- Run Spark Operator or Apache Spark on K8s for elastic batch processing
- Host multi-tenant data platform namespaces (dev/staging/prod)
- Deploy streaming workloads (Flink, Kafka consumers) with HPA/KEDA autoscaling
- Centralize pipeline tooling with GitOps (Arflux/Argo CD) and Helm charts

**When to use it:** Complex container orchestration requiring Kubernetes APIs, custom operators, multi-team namespaces, or hybrid cloud portability — when ECS simplicity is insufficient.

**Required IAM permissions (examples):** `eks:CreateCluster`, `eks:DescribeCluster`, `eks:UpdateClusterConfig`, `iam:PassRole` (cluster role), `ec2:DescribeSubnets`, `ec2:DescribeSecurityGroups`

---

## AWS CLI Commands

### Create Cluster

**Purpose:** Provision managed Kubernetes control plane for data platform workloads.

**Command:**

```bash
aws eks create-cluster \
  --name data-platform-prod \
  --version 1.29 \
  --role-arn arn:aws:iam::123456789012:role/eksClusterRole \
  --resources-vpc-config \
    subnetIds=subnet-0abc123,subnet-0def456,securityGroupIds=sg-0ghi789 \
  --logging '{"clusterLogging":[{"types":["api","audit","authenticator","controllerManager","scheduler"],"enabled":true}]}' \
  --tags Team=DataEng,Environment=prod
```

**Example Output:**

```json
{
    "cluster": {
        "name": "data-platform-prod",
        "arn": "arn:aws:eks:us-east-1:123456789012:cluster/data-platform-prod",
        "status": "CREATING",
        "version": "1.29"
    }
}
```

---

### Update kubeconfig

**Purpose:** Configure kubectl to authenticate to the EKS cluster.

**Command:**

```bash
aws eks update-kubeconfig \
  --name data-platform-prod \
  --region us-east-1 \
  --alias data-platform-prod
```

**Verify:**

```bash
kubectl get nodes
kubectl get namespaces
```

---

### Describe Cluster

**Purpose:** Retrieve endpoint, OIDC issuer, and status for integrations.

**Command:**

```bash
aws eks describe-cluster \
  --name data-platform-prod \
  --query 'cluster.{Name:name,Status:status,Endpoint:endpoint,Version:version,OIDC:identity.oidc.issuer}' \
  --output table
```

---

### Create Node Group (Managed)

**Purpose:** Add EC2 worker capacity for Spark executors and Airflow workers.

**Command:**

```bash
aws eks create-nodegroup \
  --cluster-name data-platform-prod \
  --nodegroup-name spark-workers \
  --node-role arn:aws:iam::123456789012:role/eksNodeRole \
  --subnets subnet-0abc123 subnet-0def456 \
  --scaling-config minSize=2,maxSize=20,desiredSize=4 \
  --instance-types m5.2xlarge \
  --disk-size 200 \
  --labels workload=spark,team=data-eng \
  --tags Team=DataEng
```

---

### Add Fargate Profile (Serverless Pods)

**Purpose:** Run lightweight pipeline pods without managing nodes.

**Command:**

```bash
aws eks create-fargate-profile \
  --cluster-name data-platform-prod \
  --fargate-profile-name etl-fargate \
  --pod-execution-role-arn arn:aws:iam::123456789012:role/eksFargatePodExecutionRole \
  --subnets subnet-0abc123 subnet-0def456 \
  --selectors namespace=etl-jobs,labels={workload=batch}
```

---

### List Add-ons

**Purpose:** Verify CoreDNS, kube-proxy, VPC CNI, and EBS CSI driver versions.

**Command:**

```bash
aws eks list-addons --cluster-name data-platform-prod

aws eks describe-addon \
  --cluster-name data-platform-prod \
  --addon-name aws-ebs-csi-driver \
  --query 'addon.{Name:addonName,Version:addonVersion,Status:status}'
```

---

## Advanced Commands

### Enable IRSA (IAM Roles for Service Accounts)

**Purpose:** Grant Spark/Airflow pods fine-grained S3 and Glue permissions without node-wide credentials.

**Steps:**

```bash
# 1. Associate OIDC provider
OIDC_URL=$(aws eks describe-cluster --name data-platform-prod \
  --query 'cluster.identity.oidc.issuer' --output text | sed 's|https://||')

aws iam create-open-id-connect-provider \
  --url "https://${OIDC_URL}" \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 9e99a48a9960b14926bb7f3b02e22da2b0ab7280

# 2. Create IAM role with trust policy for namespace/serviceaccount
# 3. Annotate Kubernetes service account:
#    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/SparkJobRole
```

---

### Upgrade Cluster Version

**Purpose:** Stay on supported Kubernetes versions for security patches.

**Command:**

```bash
aws eks update-cluster-version \
  --name data-platform-prod \
  --kubernetes-version 1.30

aws eks describe-update \
  --name data-platform-prod \
  --update-id <update-id-from-above>
```

Upgrade node groups after control plane upgrade completes.

---

### Access Entries (EKS API Authentication Mode)

**Purpose:** Map IAM principals to cluster access without aws-auth ConfigMap.

**Command:**

```bash
aws eks create-access-entry \
  --cluster-name data-platform-prod \
  --principal-arn arn:aws:iam::123456789012:role/DataPlatformAdmin \
  --type STANDARD

aws eks associate-access-policy \
  --cluster-name data-platform-prod \
  --principal-arn arn:aws:iam::123456789012:role/DataPlatformAdmin \
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy \
  --access-scope type=cluster
```

---

## Python (Boto3) Examples

### Describe Cluster and Build kubeconfig Context Name

```python
import boto3

eks = boto3.client("eks")

def get_cluster_info(name: str) -> dict:
    cluster = eks.describe_cluster(name=name)["cluster"]
    return {
        "endpoint": cluster["endpoint"],
        "ca_data": cluster["certificateAuthority"]["data"],
        "oidc_issuer": cluster["identity"]["oidc"]["issuer"],
        "status": cluster["status"],
    }
```

---

## Security Considerations

- Enable **control plane logging** (audit, authenticator) to CloudWatch or S3.
- Use **private endpoints** for production clusters; restrict public endpoint CIDRs if enabled.
- Implement **IRSA** for every workload accessing AWS APIs — avoid instance profile broad permissions.
- Apply **Pod Security Standards** (restricted/baseline) and **NetworkPolicies** for tenant isolation.
- Encrypt secrets with **KMS** (etcd encryption) and use External Secrets Operator for rotation.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `Unauthorized` from kubectl | IAM mapping missing | Add access entry or aws-auth ConfigMap entry |
| Pods stuck `Pending` | Insufficient node capacity or taints | Check node group scaling, instance types, tolerations |
| `ImagePullBackOff` | ECR permissions or wrong image | Verify node/Fargate role and image URI |
| Spark executor OOM | Wrong memory limits | Tune `spark.kubernetes.memoryOverheadFactor` and pod limits |
| CoreDNS failures | VPC CNI or addon mismatch | Verify addon versions match cluster K8s version |

---

## Best Practices

- Separate **node groups** by workload (Spark executors vs. system vs. Airflow).
- Use **Karpenter** or Cluster Autoscaler for elastic batch capacity.
- Install **EBS CSI** and **S3 CSI** drivers for persistent and object storage mounts.
- Namespace per **environment/team** with ResourceQuotas and LimitRanges.
- GitOps deploy pipeline manifests; pin Helm chart versions.
- Schedule **cluster upgrades** during maintenance windows; test in staging first.
