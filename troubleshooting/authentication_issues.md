# Troubleshooting — Authentication Issues

## Service Overview

Authentication failures prevent any AWS operation from succeeding. This guide covers credential resolution problems for the AWS CLI and Boto3 in data engineering environments — local development, CI/CD, EC2, Lambda, and cross-account access.

---

## AWS CLI Commands

### Verify Credentials

```bash
aws sts get-caller-identity
```

**Success output:**

```json
{
    "UserId": "AROAXXXXXXXXXXXXXXXXX:session-name",
    "Account": "123456789012",
    "Arn": "arn:aws:sts::123456789012:assumed-role/DataEngineerRole/session-name"
}
```

### Show Credential Source

```bash
aws configure list
```

**Example Output:**

```
      Name                    Value             Type    Location
      ----                    -----             ----    --------
   profile              data-engineer           manual    --profile
access_key     ****************ABCD              sso
secret_key     ****************WXYZ              sso
    region                us-east-1              config    ~/.aws/config
```

### Refresh SSO Session

```bash
aws sso login --profile data-engineer-sso
```

### Test with Explicit Profile

```bash
AWS_PROFILE=data-engineer aws sts get-caller-identity
```

### Clear and Reconfigure

```bash
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
export AWS_PROFILE=data-engineer
aws sts get-caller-identity
```

---

## Advanced Commands

### Debug Credential Chain

```bash
aws sts get-caller-identity --debug 2>&1 | grep -E "credential|auth|token|profile"
```

### Assume Role Manually

```bash
CREDS=$(aws sts assume-role \
  --role-arn arn:aws:iam::987654321098:role/DataAccessRole \
  --role-session-name debug-session \
  --output json)

export AWS_ACCESS_KEY_ID=$(echo $CREDS | jq -r .Credentials.AccessKeyId)
export AWS_SECRET_ACCESS_KEY=$(echo $CREDS | jq -r .Credentials.SecretAccessKey)
export AWS_SESSION_TOKEN=$(echo $CREDS | jq -r .Credentials.SessionToken)

aws sts get-caller-identity
```

### EC2 Instance Role Check

```bash
# On EC2 instance
curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/
curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/MyInstanceRole
```

### ECS Task Role Check

```bash
curl -s $AWS_CONTAINER_CREDENTIALS_RELATIVE_URI
```

---

## Python Boto3 Examples

### Diagnose Credential Source

```python
import boto3

session = boto3.Session(profile_name="data-engineer")
credentials = session.get_credentials()
frozen = credentials.get_frozen_credentials()

print(f"Method: {credentials.method}")
print(f"Access key: {frozen.access_key[:4]}****")
print(f"Has token: {frozen.token is not None}")

sts = session.client("sts")
print(sts.get_caller_identity())
```

### Handle Expired Credentials

```python
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

def safe_get_identity(session: boto3.Session) -> dict:
    try:
        return session.client("sts").get_caller_identity()
    except NoCredentialsError:
        raise RuntimeError(
            "No credentials found. Run 'aws sso login' or set AWS_PROFILE."
        ) from None
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ExpiredToken":
            raise RuntimeError(
                "Credentials expired. Run 'aws sso login --profile <name>'."
            ) from exc
        raise
```

---

## Security Considerations

- Never share access keys or session tokens in chat, tickets, or logs.
- Rotate compromised credentials immediately via IAM console.
- Use short-lived SSO/STS credentials — investigate any long-lived key usage.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `Unable to locate credentials` | No provider in chain | Set `AWS_PROFILE`, env vars, or instance role |
| `InvalidClientTokenId` | Wrong or deleted access key | Regenerate keys; verify key ID |
| `SignatureDoesNotMatch` | Wrong secret key or clock skew | Verify secret; sync system clock (NTP) |
| `ExpiredToken` | SSO/STS session expired | Re-login: `aws sso login` or re-assume role |
| `AccessDenied` on `sts:AssumeRole` | Trust policy blocks caller | Fix trust policy Principal and conditions |
| `ProfileNotFound` | Typo or missing config | Run `aws configure list-profiles` |
| SSO `Token has expired` | SSO session timeout | `aws sso login --profile <name>` |
| EC2 metadata unavailable | IMDSv2 required or hop limit | Configure IMDSv2; set `metadata_options` http_tokens=required |
| Wrong account returned | Profile/env mismatch | Check `AWS_PROFILE` and env var precedence |

### Credential Provider Precedence

Environment variables override profile, which overrides instance metadata:

```
1. Explicit client/session parameters
2. AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN
3. AWS_PROFILE → ~/.aws/credentials + ~/.aws/config
4. Container credentials (ECS)
5. Instance metadata (EC2/IMDS)
```

---

## Best Practices

- Run **`aws sts get-caller-identity`** at the start of every pipeline and CI job.
- Use **`AWS_PROFILE`** explicitly in scripts — don't rely on default profile.
- Set **`AWS_SDK_LOAD_CONFIG=1`** when using SSO with Terraform or Boto3.
- Configure **IMDSv2** on EC2 (`http_tokens=required`) for security.
- Use **role assumption** for cross-account — not static cross-account keys.
- Add **credential check** as first step in Glue/Lambda job code for clearer error messages.
- Document **profile names** per environment in team onboarding docs.
