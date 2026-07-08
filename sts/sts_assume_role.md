# STS — Assume Role

## Service Overview

**AWS Security Token Service (STS)** issues temporary credentials for authenticated users and roles. **`AssumeRole`** is the foundation of cross-account access, least-privilege data platform patterns, and CI/CD deployment roles in data engineering environments.

**Common use cases:**
- Data engineers accessing prod data lake buckets via a read-only cross-account role
- Glue/Lambda execution roles assumed by Step Functions or orchestration tools
- CI/CD pipelines assuming a deploy role to update Lambda and Glue jobs
- Multi-account data mesh: analytics account querying prod account S3 via assumed role

**When to use it:** Whenever long-lived credentials are insufficient or prohibited — cross-account S3 reads, temporary elevated access, and federated SSO sessions all flow through STS.

---

## AWS CLI Commands

### Get Caller Identity

**Purpose:** Verify current credentials before and after role assumption.

**Command:**

```bash
aws sts get-caller-identity
```

**Example Output:**

```json
{
    "UserId": "AIDAXXXXXXXXXXXXXXXXX",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/data-engineer"
}
```

---

### Assume Role

**Purpose:** Obtain temporary credentials for a target IAM role.

**Command:**

```bash
aws sts assume-role \
  --role-arn arn:aws:iam::987654321098:role/DataLakeReadOnlyRole \
  --role-session-name ritik-athena-session \
  --duration-seconds 3600 \
  --tags Key=Purpose,Value=ad-hoc-analysis Key=Ticket,Value=DE-4521
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
    "AssumedRoleUser": {
        "AssumedRoleId": "AROAXXXXXXXXXXXXXXXXX:ritik-athena-session",
        "Arn": "arn:aws:sts::987654321098:assumed-role/DataLakeReadOnlyRole/ritik-athena-session"
    }
}
```

**Explanation:** Export the three credential fields as environment variables to run subsequent CLI commands under the assumed role.

---

### Assume Role and Export Credentials

**Purpose:** One-liner to assume role and run a command in the same shell session.

**Command:**

```bash
CREDS=$(aws sts assume-role \
  --role-arn arn:aws:iam::987654321098:role/DataLakeReadOnlyRole \
  --role-session-name ritik-athena-session \
  --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
  --output text)

export AWS_ACCESS_KEY_ID=$(echo "$CREDS" | awk '{print $1}')
export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS" | awk '{print $2}')
export AWS_SESSION_TOKEN=$(echo "$CREDS" | awk '{print $3}')

aws sts get-caller-identity
```

**Example Output (after assume):**

```json
{
    "UserId": "AROAXXXXXXXXXXXXXXXXX:ritik-athena-session",
    "Account": "987654321098",
    "Arn": "arn:aws:sts::987654321098:assumed-role/DataLakeReadOnlyRole/ritik-athena-session"
}
```

---

### Assume Role with MFA

**Purpose:** Assume a privileged role that requires MFA authentication.

**Command:**

```bash
aws sts assume-role \
  --role-arn arn:aws:iam::123456789012:role/DataPlatformAdminRole \
  --role-session-name ritik-admin-session \
  --serial-number arn:aws:iam::123456789012:mfa/ritik \
  --token-code 123456 \
  --duration-seconds 3600
```

---

### Assume Role via Source Identity (Audit Trail)

**Purpose:** Pass source identity for CloudTrail attribution in cross-account chains.

**Command:**

```bash
aws sts assume-role \
  --role-arn arn:aws:iam::987654321098:role/DataLakeReadOnlyRole \
  --role-session-name ritik-session \
  --source-identity "ritik@company.com"
```

---

### Get Session Token (Session Credentials)

**Purpose:** Obtain session credentials from long-term IAM user keys (required for some services).

**Command:**

```bash
aws sts get-session-token \
  --duration-seconds 3600 \
  --serial-number arn:aws:iam::123456789012:mfa/ritik \
  --token-code 123456
```

**Example Output:**

```json
{
    "Credentials": {
        "AccessKeyId": "ASIAXXXXXXXXXXXXXXXX",
        "SecretAccessKey": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "SessionToken": "IQoJb3JpZ2luX2VjE...",
        "Expiration": "2025-03-01T07:00:00+00:00"
    }
}
```

---

### Assume Role With SAML (Enterprise SSO)

**Purpose:** Assume role using SAML assertion from corporate IdP (after obtaining assertion externally).

**Command:**

```bash
aws sts assume-role-with-saml \
  --role-arn arn:aws:iam::123456789012:role/DataEngineerSSO \
  --principal-arn arn:aws:iam::123456789012:saml-provider/CorporateIdP \
  --saml-assertion file://saml assertion.b64
```

---

### Decode Authorization Message (Access Denied Debugging)

**Purpose:** Decode encrypted authorization failure details from `AccessDenied` exceptions.

**Command:**

```bash
aws sts decode-authorization-message \
  --encoded-message "<EncodedMessage from error response>"
```

**Example Output:**

```json
{
    "DecodedMessage": "{\"allowed\":false,\"explicitDeny\":false,\"matchedStatements\":{\"items\":[{\"effect\":\"DENY\",\"principals\":{\"items\":[{\"providerName\":\"...\"}]}}]}}"
}
```

---

## Advanced Commands

### Assume Role with External ID (Third-Party Access)

```bash
aws sts assume-role \
  --role-arn arn:aws:iam::987654321098:role/VendorDataAccessRole \
  --role-session-name vendor-etl-session \
  --external-id "unique-vendor-identifier-abc123"
```

### Assume Role via AWS SSO (CLI v2)

```bash
aws sso login --profile data-engineer-prod
aws sts get-caller-identity --profile data-engineer-prod
```

### Chain Roles (Cross-Account then Downstream)

```bash
# Step 1: Assume cross-account role in data account
CREDS1=$(aws sts assume-role \
  --role-arn arn:aws:iam::987654321098:role/CrossAccountAccess \
  --role-session-name step1 \
  --output json)

export AWS_ACCESS_KEY_ID=$(echo "$CREDS1" | jq -r '.Credentials.AccessKeyId')
export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS1" | jq -r '.Credentials.SecretAccessKey')
export AWS_SESSION_TOKEN=$(echo "$CREDS1" | jq -r '.Credentials.SessionToken')

# Step 2: From data account, assume workload-specific role
aws sts assume-role \
  --role-arn arn:aws:iam::987654321098:role/GlueETLRole \
  --role-session-name step2
```

### Tag Session for Cost Allocation

```bash
aws sts assume-role \
  --role-arn arn:aws:iam::987654321098:role/DataLakeReadOnlyRole \
  --role-session-name cost-tagged-session \
  --tags Key=CostCenter,Value=DE-100 Key=Project,Value=orders-analytics \
  --transitive-tag-keys CostCenter Project
```

---

## Python Boto3 Examples

### Basic — Assume Role

```python
import boto3

sts = boto3.client("sts")

response = sts.assume_role(
    RoleArn="arn:aws:iam::987654321098:role/DataLakeReadOnlyRole",
    RoleSessionName="python-athena-session",
    DurationSeconds=3600,
)
creds = response["Credentials"]

session = boto3.Session(
    aws_access_key_id=creds["AccessKeyId"],
    aws_secret_access_key=creds["SecretAccessKey"],
    aws_session_token=creds["SessionToken"],
)
s3 = session.client("s3")
print(s3.list_buckets()["Buckets"])
```

### Production-Ready — Role Assumer with Auto-Refresh

```python
import logging
from datetime import datetime, timezone

import boto3
from botocore.credentials import RefreshableCredentials
from botocore.session import get_session

logger = logging.getLogger(__name__)


def assumed_role_session(
    role_arn: str,
    session_name: str,
    duration: int = 3600,
    base_session: boto3.Session | None = None,
) -> boto3.Session:
    base = base_session or boto3.Session()
    sts = base.client("sts")

    def refresh():
        resp = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName=session_name,
            DurationSeconds=duration,
        )
        c = resp["Credentials"]
        logger.info("Assumed role %s until %s", role_arn, c["Expiration"])
        return {
            "access_key": c["AccessKeyId"],
            "secret_key": c["SecretAccessKey"],
            "token": c["SessionToken"],
            "expiry_time": c["Expiration"].isoformat(),
        }

    creds = RefreshableCredentials.create_from_metadata(
        metadata=refresh(),
        refresh_using=refresh,
        method="sts-assume-role",
    )
    botocore_session = get_session()
    botocore_session._credentials = creds
    return boto3.Session(botocore_session=botocore_session)
```

### Cross-Account S3 Read

```python
import boto3


def list_cross_account_prefix(role_arn: str, bucket: str, prefix: str) -> list[str]:
    session = assumed_role_session(role_arn, "cross-account-list")
    s3 = session.client("s3")

    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys
```

---

## Security Considerations

- Always use **ExternalId** when third parties assume roles into your account.
- Set **`MaxSessionDuration`** on roles appropriately (1–12 hours); use shortest duration needed.
- Require **MFA** for privileged roles via IAM condition: `"Bool": {"aws:MultiFactorAuthPresent": "true"}`.
- Scope **`sts:AssumeRole`** with **`aws:PrincipalArn`** and **`aws:SourceAccount`** conditions.
- Never log **session tokens** or temporary secret keys.
- Enable **CloudTrail** for all `AssumeRole` events; alert on unusual role assumption patterns.
- Prefer **AWS SSO / IAM Identity Center** over manual role assumption for human access.

---

## Troubleshooting

| Error / Symptom | Root Cause | Resolution |
|-----------------|------------|------------|
| `AccessDenied` on AssumeRole | Trust policy or IAM policy blocks caller | Verify role trust policy allows source principal |
| `AccessDenied` after assume | Role lacks permissions for target action | Check role permissions policy; use `decode-authorization-message` |
| `ExpiredToken` | Session exceeded duration | Re-assume role; implement auto-refresh |
| `RegionDisabledException` | STS regional endpoint issue | Use correct regional STS endpoint or `AWS_STS_REGIONAL_ENDPOINTS=regional` |
| External ID mismatch | Wrong or missing ExternalId | Confirm ExternalId matches role trust policy exactly |
| MFA required error | Role policy requires MFA | Pass `--serial-number` and `--token-code` |
| Wrong account after assume | Credentials not exported | Verify all three env vars set including `AWS_SESSION_TOKEN` |

---

## Best Practices

- Use descriptive **`RoleSessionName`** values: `<user>-<purpose>-<ticket>` for audit trails.
- Pass **`SourceIdentity`** in cross-account chains for end-user attribution in CloudTrail.
- Default session duration to **1 hour** for human access; extend only when justified.
- Structure multi-account access: **hub account roles** → **spoke account data roles** with minimal scope.
- Never embed assumed-role credentials in **Git, logs, or tickets**.
- Use **`aws sso login`** for daily work; reserve programmatic `assume_role` for automation.
- Test role assumption with **`get-caller-identity`** immediately after every assume call.
- Document every cross-account role with: purpose, trust policy, permission boundary, and owner team.
