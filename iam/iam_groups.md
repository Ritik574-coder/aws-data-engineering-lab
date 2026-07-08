# IAM — Groups

## Service Overview

IAM groups collect users under shared permission sets, simplifying access management for teams like Data Engineering or Analytics.

---

## AWS CLI Commands

### Create Group

```bash
aws iam create-group --group-name DataEngineers
```

### Add User to Group

```bash
aws iam add-user-to-group --group-name DataEngineers --user-name jane.doe
```

### Attach Policy to Group

```bash
aws iam attach-group-policy \
  --group-name DataEngineers \
  --policy-arn arn:aws:iam::123456789012:policy/DataLakeReadWrite
```

### List Group Members

```bash
aws iam get-group --group-name DataEngineers
```

---

## Advanced Commands

```bash
aws iam list-groups-for-user --user-name jane.doe
aws iam list-attached-group-policies --group-name DataEngineers
```

---

## Python (Boto3) Examples

```python
import boto3

iam = boto3.client("iam")

def ensure_group_membership(group: str, username: str) -> None:
    groups = iam.list_groups_for_user(UserName=username)["Groups"]
    if not any(g["GroupName"] == group for g in groups):
        iam.add_user_to_group(GroupName=group, UserName=username)
```

---

## Security Considerations

- Groups cannot be assigned to roles — only users.
- Avoid overly broad managed policies on groups; use custom policies scoped to resources.
- Review group membership quarterly.

---

## Best Practices

- One group per **function** (e.g., `DataEngineers`, `AnalyticsReadOnly`).
- Combine groups with **permission boundaries** for defense in depth.
- Document group purpose and policy attachments in runbooks.
