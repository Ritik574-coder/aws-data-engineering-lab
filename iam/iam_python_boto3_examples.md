# IAM — Python Boto3 Examples

## Service Overview

Programmatic IAM management for automation — user provisioning, role creation, policy attachment, and permission auditing.

---

## Basic Examples

```python
import boto3

iam = boto3.client("iam")
roles = iam.list_roles(MaxItems=50)["Roles"]
for role in roles:
    print(role["RoleName"], role["Arn"])
```

---

## Production Examples

### Create Role with Inline Policy

```python
import json
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
iam = boto3.client("iam")


def create_glue_role(role_name: str, bucket_arn: str) -> str:
    trust = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "glue.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }],
    }
    try:
        role = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust),
            Description="Glue ETL execution role",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "EntityAlreadyExists":
            role = iam.get_role(RoleName=role_name)
        else:
            raise

    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
            "Resource": [bucket_arn, f"{bucket_arn}/*"],
        }],
    }
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="S3DataLakeAccess",
        PolicyDocument=json.dumps(policy),
    )
    return role["Role"]["Arn"]
```

### Paginate All Users

```python
paginator = iam.get_paginator("list_users")
for page in paginator.paginate():
    for user in page["Users"]:
        print(user["UserName"])
```

---

## Error Handling

```python
from botocore.exceptions import ClientError

try:
    iam.delete_user(UserName="ghost-user")
except ClientError as exc:
    if exc.response["Error"]["Code"] == "DeleteConflict":
        print("Remove policies and group memberships first")
    else:
        raise
```

---

## Best Practices

- Use **resource tags** on IAM roles for cost and ownership.
- Never log full policy documents containing sensitive ARNs in production logs.
- Test policies with **`simulate_principal_policy`** before attaching.
