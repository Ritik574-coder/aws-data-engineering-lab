# AWS Organizations — Multi-Account Management

## Service Overview

**AWS Organizations** helps you centrally manage and govern multiple AWS accounts. It supports organizational units (OUs), service control policies (SCPs), consolidated billing, and account creation automation.

**Common use cases:**
- Separate dev/staging/prod data platform accounts
- Enforce guardrails (no public S3, require encryption) via SCPs
- Centralize CloudTrail, Config, and Security Hub in a security account
- Allocate costs by account/OU for data engineering teams

**When to use it:** When your data platform spans multiple AWS accounts and you need centralized policy enforcement, billing, and account lifecycle management.

---

## AWS CLI Commands

### Describe Organization

**Purpose:** Verify organization root and feature set.

**Command:**

```bash
aws organizations describe-organization
```

**Example Output:**

```json
{
    "Organization": {
        "Id": "o-abc123def4",
        "Arn": "arn:aws:organizations::123456789012:organization/o-abc123def4",
        "FeatureSet": "ALL",
        "MasterAccountId": "123456789012",
        "MasterAccountEmail": "billing@mycompany.com"
    }
}
```

---

### List Accounts

```bash
aws organizations list-accounts \
  --query 'Accounts[*].[Id,Name,Status,Email]' \
  --output table
```

---

### Create Account

**Purpose:** Provision a new data sandbox account.

**Command:**

```bash
aws organizations create-account \
  --email data-sandbox-admin@mycompany.com \
  --account-name data-sandbox \
  --role-name OrganizationAccountAccessRole \
  --tags Key=Team,Value=DataEngineering Key=Environment,Value=sandbox
```

**Note:** Account creation is asynchronous — poll with `describe-create-account-status`.

```bash
aws organizations describe-create-account-status \
  --create-account-request-id car-abc123def456
```

---

### List Organizational Units

```bash
aws organizations list-roots
aws organizations list-organizational-units-for-parent --parent-id r-abcd
```

---

### Create Organizational Unit

```bash
aws organizations create-organizational-unit \
  --parent-id r-abcd \
  --name DataPlatform
```

---

### Move Account to OU

```bash
aws organizations move-account \
  --account-id 987654321098 \
  --source-parent-id r-abcd \
  --destination-parent-id ou-abcd-efgh1234
```

---

### Create Service Control Policy (SCP)

**Purpose:** Deny public S3 buckets across all data platform accounts.

**Command:**

```bash
aws organizations create-policy \
  --name DenyPublicS3 \
  --description "Prevent public S3 bucket policies and ACLs" \
  --type SERVICE_CONTROL_POLICY \
  --content file://deny-public-s3-scp.json
```

`deny-public-s3-scp.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyPublicS3",
      "Effect": "Deny",
      "Action": [
        "s3:PutBucketPublicAccessBlock",
        "s3:PutBucketAcl",
        "s3:PutBucketPolicy"
      ],
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "aws:PrincipalAccount": ["123456789012"]
        }
      }
    }
  ]
}
```

---

### Attach SCP to OU

```bash
aws organizations attach-policy \
  --policy-id p-abc123def4 \
  --target-id ou-abcd-efgh1234
```

---

### List Policies for Target

```bash
aws organizations list-policies-for-target \
  --target-id ou-abcd-efgh1234 \
  --filter SERVICE_CONTROL_POLICY
```

---

### Enable AWS Service Access (Delegated Admin)

```bash
aws organizations enable-aws-service-access \
  --service-principal backup.amazonaws.com

aws organizations register-delegated-administrator \
  --account-id 111222333444 \
  --service-principal backup.amazonaws.com
```

---

## Advanced Commands

### Assume Role into Member Account

```bash
aws sts assume-role \
  --role-arn arn:aws:iam::987654321098:role/OrganizationAccountAccessRole \
  --role-session-name org-admin-session
```

### Invite Existing Account

```bash
aws organizations invite-account-to-organization \
  --target Id=555666777888,Type=ACCOUNT
```

### List Tags on Account

```bash
aws organizations list-tags-for-resource \
  --resource-id 987654321098
```

### Close Account (with safeguards)

```bash
aws organizations close-account --account-id 987654321098
```

**Warning:** Irreversible after closure period. Use only for decommissioned sandboxes.

---

## Python Boto3 Examples

```python
import boto3

org = boto3.client("organizations")

# List all active accounts
paginator = org.get_paginator("list_accounts")
for page in paginator.paginate():
    for account in page["Accounts"]:
        if account["Status"] == "ACTIVE":
            print(account["Id"], account["Name"])
```

---

## Security Considerations

- **SCPs are guardrails, not grants** — they filter permissions; IAM policies still required in each account.
- Restrict Organizations API access to a small set of break-glass admin roles.
- Enable **all features** (`FeatureSet: ALL`) for SCPs and consolidated billing.
- Use **delegated administrator** accounts for Security Hub, GuardDuty, and Backup — not the management account for daily ops.
- Never store root credentials; use IAM Identity Center for human access across accounts.
- Audit SCP changes via CloudTrail in the management account.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `AccessDeniedException` | Caller lacks org admin permissions | Use management account admin role |
| `AccountAlreadyRegisteredException` | Email already used | Use unique email per account |
| SCP not blocking action | SCP uses Allow-only or wrong effect | SCPs cannot grant — use Deny statements |
| `ConstraintViolationException` | OU depth or account limit | Request quota increase |
| Cannot assume member role | Role name mismatch or SCP deny | Verify `OrganizationAccountAccessRole` exists |

---

## Best Practices

- **Structure OUs by function** — `Security`, `Infrastructure`, `DataPlatform/NonProd`, `DataPlatform/Prod`.
- **Apply SCPs at OU level** — inherit to child accounts; avoid attaching to root unless global.
- **Use account tags** for cost allocation and automation (`Environment`, `CostCenter`).
- **Automate account vending** with AWS Control Tower or custom Step Functions workflows.
- **Centralize logging** — org-trail in security account with log archive S3 bucket.
- **Limit management account usage** — billing and org admin only; no workloads.
- **Document SCP intent** — each policy should have a clear security rationale and exception process.
