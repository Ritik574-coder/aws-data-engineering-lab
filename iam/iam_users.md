# IAM — Users

## Service Overview

**AWS IAM (Identity and Access Management)** controls who can access AWS resources and how. IAM users represent individual identities (human or service).

**Common use cases:**
- Service accounts for CI/CD pipelines
- Break-glass admin accounts (discouraged for daily use)
- Cross-team developer access with scoped permissions

**When to use:** Prefer IAM roles and SSO for humans; use IAM users sparingly for legacy integrations that cannot assume roles.

---

## AWS CLI Commands

### Create User

```bash
aws iam create-user --user-name etl-service-user \
  --tags Key=Team,Value=DataEngineering Key=Environment,Value=prod
```

### List Users

```bash
aws iam list-users --query 'Users[].{Name:UserName,Created:CreateDate}' --output table
```

### Create Access Key

```bash
aws iam create-access-key --user-name etl-service-user
```

**Example Output:**

```json
{
    "AccessKey": {
        "AccessKeyId": "AKIA...",
        "SecretAccessKey": "...",
        "Status": "Active",
        "CreateDate": "2025-03-01T10:00:00Z"
    }
}
```

### Attach Managed Policy

```bash
aws iam attach-user-policy \
  --user-name etl-service-user \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
```

### Delete Access Key

```bash
aws iam delete-access-key --user-name etl-service-user --access-key-id AKIA...
```

---

## Advanced Commands

### Filter Users by Tag

```bash
aws iam list-users \
  --query 'Users[?Tags[?Key==`Team` && Value==`DataEngineering`]].UserName' \
  --output text
```

### Get Login Profile (Console Access)

```bash
aws iam get-login-profile --user-name data-analyst
```

---

## Python (Boto3) Examples

```python
import boto3
from botocore.exceptions import ClientError

iam = boto3.client("iam")

def create_etl_user(username: str) -> None:
    try:
        iam.create_user(
            UserName=username,
            Tags=[{"Key": "Purpose", "Value": "ETL"}],
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "EntityAlreadyExists":
            raise
```

---

## Security Considerations

- **Disable console access** for service users; use access keys only when necessary.
- Rotate access keys every 90 days; prefer **IAM roles** instead.
- Enable **MFA** for all human IAM users with console access.
- Never commit access keys to Git — use Secrets Manager or CI/CD OIDC.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `LimitExceeded` | Max 2 access keys per user | Delete unused key before creating new |
| `DeleteConflict` | User has attached policies/groups | Detach policies and remove from groups first |

---

## Best Practices

- Use **naming conventions**: `{team}-{purpose}-{env}`.
- Prefer **AWS IAM Identity Center (SSO)** for human access.
- Audit users with **Access Analyzer** and **credential reports**.
