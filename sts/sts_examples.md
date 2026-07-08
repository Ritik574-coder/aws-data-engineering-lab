# STS — Examples

## Service Overview

**AWS STS** provides multiple APIs beyond `AssumeRole`: identity verification, federated access, web identity (OIDC), and credential scoping. Data engineering teams encounter STS whenever pipelines run under IAM roles, GitHub Actions deploy via OIDC, or Kubernetes workloads use IRSA.

**Common use cases:**
- Verify pipeline identity at runtime with `GetCallerIdentity`
- GitHub Actions OIDC → IAM role for Lambda/Glue deployment
- EKS pod identity via `AssumeRoleWithWebIdentity`
- Scoped-down credentials with session policies for read-only prod access

**When to use it:** Any time you need to confirm who is calling AWS APIs, obtain federated credentials, or implement secure CI/CD without long-lived secrets.

---

## AWS CLI Commands

### Get Caller Identity (Health Check)

**Purpose:** Confirm which principal is executing pipeline commands.

**Command:**

```bash
aws sts get-caller-identity
```

**Example Output:**

```json
{
    "UserId": "AROAXXXXXXXXXXXXXXXXX:GitHubActions-Deploy",
    "Account": "123456789012",
    "Arn": "arn:aws:sts::123456789012:assumed-role/GitHubDeployRole/GitHubActions-Deploy"
}
```

---

### Assume Role with Web Identity (OIDC — GitHub Actions Pattern)

**Purpose:** Exchange an OIDC token for AWS credentials (typically handled by CI; CLI shown for testing).

**Command:**

```bash
aws sts assume-role-with-web-identity \
  --role-arn arn:aws:iam::123456789012:role/GitHubDeployRole \
  --role-session-name GitHubActions-Deploy \
  --web-identity-token file://oidc-token.jwt \
  --duration-seconds 3600
```

**Example Output:**

```json
{
    "Credentials": {
        "AccessKeyId": "ASIAXXXXXXXXXXXXXXXX",
        "SecretAccessKey": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "SessionToken": "IQoJb3JpZ2luX2VjE...",
        "Expiration": "2025-03-01T07:00:00+00:00"
    },
    "SubjectFromWebIdentityToken": "repo:myorg/aws-data-engineering-lab:ref:refs/heads/main",
    "Audience": "sts.amazonaws.com"
}
```

---

### Assume Role with Session Policy (Scoped Access)

**Purpose:** Further restrict permissions for a single session (read-only S3 prefix).

**Command:**

```bash
aws sts assume-role \
  --role-arn arn:aws:iam::987654321098:role/DataLakeReadOnlyRole \
  --role-session-name scoped-read-session \
  --policy '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::analytics-curated",
        "arn:aws:s3:::analytics-curated/orders/*"
      ]
    }]
  }'
```

**Explanation:** The session policy intersects with the role's permissions policy — effective permissions are the union restricted by the session policy boundary.

---

### Get Federation Token (Legacy IAM User Delegation)

**Purpose:** Delegate short-term access to an IAM user with an inline policy cap.

**Command:**

```bash
aws sts get-federation-token \
  --name etl-operator-session \
  --policy-arns arn:aws:iam::123456789012:policy/AthenaReadOnlyPolicy \
  --duration-seconds 3600
```

**Example Output (abbreviated):**

```json
{
    "Credentials": {
        "AccessKeyId": "ASIAXXXXXXXXXXXXXXXX",
        "SecretAccessKey": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "SessionToken": "IQoJb3JpZ2luX2VjE...",
        "Expiration": "2025-03-01T07:00:00+00:00"
    },
    "FederatedUser": {
        "Arn": "arn:aws:sts::123456789012:federated-user/etl-operator-session",
        "FederatedUserId": "123456789012:etl-operator-session"
    }
}
```

---

### Get Access Key Info

**Purpose:** Identify which IAM user owns an access key (security audit).

**Command:**

```bash
aws sts get-access-key-info --access-key-id AKIAXXXXXXXXXXXXXXXX
```

**Example Output:**

```json
{
    "Account": "123456789012",
    "UserArn": "arn:aws:iam::123456789012:user/legacy-etl-service"
}
```

---

### Assume Root (Not Allowed — Reference)

**Purpose:** Document that root account credentials should never be used for AssumeRole patterns.

**Note:** Root account access keys should be deleted. All automation must use IAM roles with STS.

---

## Advanced Commands

### Credential Process (AWS Config Profile)

```ini
# ~/.aws/config
[profile cross-account-data-lake]
role_arn = arn:aws:iam::987654321098:role/DataLakeReadOnlyRole
source_profile = default
region = us-east-1
duration_seconds = 3600
role_session_name = ritik-data-lake
```

```bash
aws s3 ls s3://analytics-curated/ --profile cross-account-data-lake
```

### GitHub Actions OIDC Trust Policy (Reference)

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"},
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {"token.actions.githubusercontent.com:aud": "sts.amazonaws.com"},
      "StringLike": {"token.actions.githubusercontent.com:sub": "repo:myorg/aws-data-engineering-lab:*"}
    }
  }]
}
```

### Decode Authorization Failure

```bash
aws sts decode-authorization-message \
  --encoded-message "$(echo 'AccessDenied' error payload EncodedMessage field)"
```

### IAM Identity Center (SSO) Login Flow

```bash
aws configure sso
aws sso login --profile data-engineer
aws sts get-caller-identity --profile data-engineer
```

---

## Python Boto3 Examples

### Identity Check at Pipeline Startup

```python
import logging

import boto3

logger = logging.getLogger(__name__)


def verify_pipeline_identity(expected_account: str, expected_role_suffix: str) -> dict:
    identity = boto3.client("sts").get_caller_identity()
    account = identity["Account"]
    arn = identity["Arn"]

    if account != expected_account:
        raise RuntimeError(f"Wrong account: expected {expected_account}, got {account}")
    if expected_role_suffix not in arn:
        raise RuntimeError(f"Wrong role: expected *{expected_role_suffix}* in {arn}")

    logger.info("Pipeline identity verified: %s", arn)
    return identity
```

### Assume Role with Session Policy

```python
import json

import boto3


def assume_readonly_orders_prefix(role_arn: str) -> boto3.Session:
    sts = boto3.client("sts")
    session_policy = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:ListBucket"],
            "Resource": [
                "arn:aws:s3:::analytics-curated",
                "arn:aws:s3:::analytics-curated/orders/*",
            ],
        }],
    })

    resp = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName="orders-readonly",
        Policy=session_policy,
        DurationSeconds=3600,
    )
    c = resp["Credentials"]
    return boto3.Session(
        aws_access_key_id=c["AccessKeyId"],
        aws_secret_access_key=c["SecretAccessKey"],
        aws_session_token=c["SessionToken"],
    )
```

### Production-Ready — Multi-Account Session Factory

```python
import logging
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

ACCOUNT_ROLES = {
    "dev": "arn:aws:iam::111111111111:role/DataPlatformRole",
    "staging": "arn:aws:iam::222222222222:role/DataPlatformRole",
    "prod": "arn:aws:iam::333333333333:role/DataPlatformRole",
}


@lru_cache(maxsize=3)
def get_session_for_env(env: str) -> boto3.Session:
    role_arn = ACCOUNT_ROLES.get(env)
    if not role_arn:
        raise ValueError(f"Unknown environment: {env}")

    sts = boto3.client("sts")
    try:
        resp = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName=f"data-platform-{env}",
            DurationSeconds=3600,
            Tags=[{"Key": "Environment", "Value": env}],
        )
    except ClientError as exc:
        logger.error("Failed to assume %s role: %s", env, exc.response["Error"]["Message"])
        raise

    c = resp["Credentials"]
    return boto3.Session(
        aws_access_key_id=c["AccessKeyId"],
        aws_secret_access_key=c["SecretAccessKey"],
        aws_session_token=c["SessionToken"],
    )


def get_glue_client(env: str):
    return get_session_for_env(env).client("glue")
```

### Lambda Execution Context Identity

```python
import boto3


def lambda_handler(event, context):
    identity = boto3.client("sts").get_caller_identity()
    # identity["Arn"] -> arn:aws:sts::123456789012:assumed-role/LambdaRole/function-name
    return {
        "role": identity["Arn"],
        "account": identity["Account"],
    }
```

### GitHub Actions Equivalent (boto3 in deploy script)

```python
import boto3

# When running in GitHub Actions with OIDC configured via aws-actions/configure-aws-credentials,
# boto3 automatically uses the assumed role credentials from the environment.
def deploy_glue_job(job_name: str, artifact_bucket: str, artifact_key: str) -> None:
    identity = boto3.client("sts").get_caller_identity()
    print(f"Deploying as {identity['Arn']}")

    glue = boto3.client("glue")
    glue.update_job(
        JobName=job_name,
        JobUpdate={
            "Role": f"arn:aws:iam::{identity['Account']}:role/GlueETLRole",
            "Command": {
                "Name": "glueetl",
                "ScriptLocation": f"s3://{artifact_bucket}/{artifact_key}",
                "PythonVersion": "3",
            },
            "GlueVersion": "4.0",
            "NumberOfWorkers": 5,
            "WorkerType": "G.1X",
        },
    )
```

---

## Security Considerations

- Use **OIDC federation** (GitHub, GitLab) instead of storing AWS access keys in CI secrets.
- Apply **session policies** to limit blast radius of assumed roles in prod.
- Rotate and eliminate **long-term IAM user keys** — audit with `get-access-key-info`.
- Restrict **`sts:AssumeRole`** in service control policies (SCPs) at the OU level.
- Log and monitor all **`AssumeRoleWithWebIdentity`** calls for CI/CD roles.
- Never pass **root account credentials** to any SDK or CLI tool.

---

## Troubleshooting

| Error / Symptom | Root Cause | Resolution |
|-----------------|------------|------------|
| `Unable to locate credentials` | No base credentials for role chain | Configure source profile or instance role |
| OIDC assume fails in CI | Trust policy repo/branch mismatch | Fix `sub` condition in role trust policy |
| Session policy too restrictive | Intersection empty with role policy | Broaden session policy or role policy |
| `ExpiredToken` in long-running job | Session outlived duration | Use refreshable credentials or shorter job runtime |
| Wrong identity in Lambda | Checking during cold start only | Identity is stable per execution environment |
| SSO login expired | SSO session timeout | Re-run `aws sso login` |

---

## Best Practices

- Call **`get_caller_identity()`** at the start of every deploy script and pipeline job.
- Configure **`~/.aws/config` role chains** for daily cross-account work instead of manual export.
- Use **GitHub OIDC** with tight `sub` conditions (`repo:org/name:ref:refs/heads/main`).
- Cache assumed-role sessions with **`lru_cache`** or refreshable credentials — do not assume on every API call.
- Tag sessions with **`Environment`**, **`Pipeline`**, and **`Ticket`** for cost and audit correlation.
- Implement **`verify_pipeline_identity()`** guards before any prod write operation.
- Document all federation paths (SSO, OIDC, cross-account) in a central runbook.
- Prefer **IAM roles on compute** (Lambda, Glue, EC2) over any form of embedded credentials.
