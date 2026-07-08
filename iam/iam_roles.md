# IAM — Roles

## Service Overview

IAM roles provide temporary credentials via STS. They are the **preferred** identity for EC2, Lambda, Glue, ECS, and cross-account access.

**Common use cases:**
- Glue job execution role
- Lambda function role
- Cross-account S3/Athena access via assume role
- CI/CD OIDC federation (GitHub Actions → AWS)

---

## AWS CLI Commands

### Create Role with Trust Policy

```bash
aws iam create-role \
  --role-name GlueETLRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "glue.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'
```

### Attach Policy to Role

```bash
aws iam attach-role-policy \
  --role-name GlueETLRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole
```

### Assume Role

```bash
aws sts assume-role \
  --role-arn arn:aws:iam::123456789012:role/CrossAccountDataAccess \
  --role-session-name etl-session \
  --duration-seconds 3600
```

### Get Role

```bash
aws iam get-role --role-name GlueETLRole \
  --query 'Role.{Name:RoleName,Arn:Arn,MaxSession:MaxSessionDuration}'
```

---

## Advanced Commands

### Update Max Session Duration

```bash
aws iam update-role \
  --role-name GlueETLRole \
  --max-session-duration 43200
```

### List Instance Profiles (EC2)

```bash
aws iam list-instance-profiles-for-role --role-name EC2ETLRole
```

---

## Python (Boto3) Examples

```python
import boto3

def assume_cross_account(role_arn: str, session_name: str = "boto-session"):
    sts = boto3.client("sts")
    creds = sts.assume_role(RoleArn=role_arn, RoleSessionName=session_name)["Credentials"]
    return boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )
```

---

## Security Considerations

- Restrict **trust policies** to specific principals and external IDs for cross-account.
- Use **session policies** to further limit assumed role permissions.
- Enable **CloudTrail** to audit `AssumeRole` events.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `AccessDenied` on AssumeRole | Trust policy mismatch | Verify Principal in trust policy |
| `MalformedPolicyDocument` | Invalid JSON | Validate trust policy syntax |

---

## Best Practices

- One role per **workload** (Glue job, Lambda, EMR cluster).
- Use **IAM roles anywhere** instead of embedding credentials.
- Apply **least privilege** with custom inline or customer-managed policies.
