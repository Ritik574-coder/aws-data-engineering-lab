# Boto3 — Authentication

## Service Overview

Boto3 resolves AWS credentials through a **credential provider chain**. Understanding authentication is essential for data pipelines running locally, on EC2, in Lambda, ECS, or CI/CD systems.

**Credential sources (in order):**
1. Explicit parameters passed to `Session` or `client()`
2. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`)
3. Shared credentials file (`~/.aws/credentials`)
4. AWS config file (`~/.aws/config`) — profiles, SSO, role assumption
5. Instance/container metadata (EC2 IMDS, ECS task role, Lambda execution role)

**When to use each:** Local dev uses profiles or SSO; production workloads use IAM roles; cross-account uses STS `AssumeRole`.

---

## AWS CLI Commands

### Verify Current Identity

```bash
aws sts get-caller-identity
```

**Example Output:**

```json
{
    "UserId": "AIDAXXXXXXXXXXXXXXXXX",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:role/DataEngineerRole"
}
```

---

### Configure Profile

```bash
aws configure --profile data-engineer
aws configure set region us-east-1 --profile data-engineer
```

---

### SSO Login

```bash
aws configure sso --profile data-engineer-sso
aws sso login --profile data-engineer-sso
aws sts get-caller-identity --profile data-engineer-sso
```

---

### Assume Role

```bash
aws sts assume-role \
  --role-arn arn:aws:iam::987654321098:role/CrossAccountDataAccess \
  --role-session-name etl-session \
  --external-id unique-external-id-12345
```

Export returned credentials:

```bash
export AWS_ACCESS_KEY_ID=<AccessKeyId>
export AWS_SECRET_ACCESS_KEY=<SecretAccessKey>
export AWS_SESSION_TOKEN=<SessionToken>
```

---

### Assume Role with Web Identity (OIDC — GitHub Actions)

```bash
aws sts assume-role-with-web-identity \
  --role-arn arn:aws:iam::123456789012:role/GitHubActionsDeployRole \
  --role-session-name github-deploy \
  --web-identity-token file://token.jwt
```

---

## Advanced Commands

### Credential Process (Custom Provider)

`~/.aws/config`:

```ini
[profile custom-vault]
credential_process = /usr/local/bin/fetch-aws-creds --profile data-engineer
region = us-east-1
```

### Named Profile with Role Chaining

```ini
[profile data-prod]
role_arn = arn:aws:iam::987654321098:role/DataEngineerRole
source_profile = data-engineer-sso
region = us-east-1
external_id = unique-external-id-12345
```

### MFA-Protected Role Assumption

```ini
[profile data-admin]
role_arn = arn:aws:iam::123456789012:role/AdminRole
source_profile = base-user
mfa_serial = arn:aws:iam::123456789012:mfa/admin-device
```

---

## Python Boto3 Examples

### Default Credential Chain

```python
import boto3

# Uses environment, ~/.aws/credentials, or instance metadata
session = boto3.Session()
sts = session.client("sts")
print(sts.get_caller_identity())
```

### Named Profile

```python
session = boto3.Session(profile_name="data-engineer", region_name="us-east-1")
s3 = session.client("s3")
```

### Explicit Credentials (Avoid in Production)

```python
session = boto3.Session(
    aws_access_key_id="AKIA...",
    aws_secret_access_key="...",
    aws_session_token="...",  # optional, for temporary creds
    region_name="us-east-1",
)
```

### Assume Role Programmatically

```python
import boto3

def assumed_role_session(role_arn: str, session_name: str = "boto3-session") -> boto3.Session:
    sts = boto3.client("sts")
    response = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName=session_name,
    )
    creds = response["Credentials"]
    return boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )

session = assumed_role_session("arn:aws:iam::987654321098:role/DataAccessRole")
s3 = session.client("s3")
```

### Refreshable Credentials (Long-Running Processes)

```python
import boto3
from botocore.credentials import RefreshableCredentials
from botocore.session import get_session

ROLE_ARN = "arn:aws:iam::987654321098:role/DataAccessRole"


def refresh():
    sts = boto3.client("sts")
    resp = sts.assume_role(RoleArn=ROLE_ARN, RoleSessionName="refreshable")
    c = resp["Credentials"]
    return {
        "access_key": c["AccessKeyId"],
        "secret_key": c["SecretAccessKey"],
        "token": c["SessionToken"],
        "expiry_time": c["Expiration"].isoformat(),
    }


session_credentials = RefreshableCredentials.create_from_metadata(
    metadata=refresh(),
    refresh_using=refresh,
    method="sts-assume-role",
)
botocore_session = get_session()
botocore_session._credentials = session_credentials
session = boto3.Session(botocore_session=botocore_session)
```

---

## Security Considerations

- **Never hardcode access keys** in source code, notebooks, or Docker images.
- Prefer **IAM roles** over long-lived access keys for EC2, Lambda, ECS, and Glue.
- Use **SSO / IAM Identity Center** for human access — short-lived credentials.
- Require **ExternalId** on cross-account role trust policies.
- Rotate access keys if used; monitor with IAM credential report.
- Scope session tags and transitive tags for attribute-based access control (ABAC).

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `NoCredentialsError` | No provider returned credentials | Configure profile, env vars, or instance role |
| `ExpiredToken` | Session token expired | Re-run SSO login or refresh assumed role |
| `AccessDenied` on AssumeRole | Trust policy or ExternalId mismatch | Verify trust policy Principal and conditions |
| Wrong account in `get-caller-identity` | Wrong profile active | Set `AWS_PROFILE` or pass `profile_name` |
| SSO token not found | SSO session expired | Run `aws sso login --profile <name>` |

---

## Best Practices

- Set `AWS_PROFILE` and `AWS_DEFAULT_REGION` explicitly in scripts and CI.
- Use **role chaining** from a base SSO profile rather than storing multiple keys.
- In Lambda/Glue/ECS, rely on execution roles — no credential configuration needed.
- Log `get_caller_identity()` at pipeline startup for audit trail.
- Use **aws-vault** or similar tools for local credential isolation.
- Validate credentials before long-running ETL jobs to fail fast.
