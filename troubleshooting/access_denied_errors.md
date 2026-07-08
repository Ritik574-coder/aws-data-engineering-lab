# Troubleshooting — Access Denied Errors

## Service Overview

`AccessDenied` and `403 Forbidden` errors indicate the caller is authenticated but not authorized for the requested action. In data engineering, these commonly involve IAM policies, bucket policies, Lake Formation permissions, SCPs, KMS key policies, and VPC endpoint policies.

---

## AWS CLI Commands

### Confirm Identity

```bash
aws sts get-caller-identity
```

### Simulate Policy Evaluation

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/GlueETLRole \
  --action-names s3:GetObject s3:PutObject s3:ListBucket \
  --resource-arns \
    arn:aws:s3:::my-data-lake-raw \
    arn:aws:s3:::my-data-lake-raw/orders/* \
  --context-entries '[
    {
      "ContextKeyName": "aws:RequestedRegion",
      "ContextKeyValues": ["us-east-1"],
      "ContextKeyType": "string"
    }
  ]'
```

**Example Output:**

```json
{
    "EvaluationResults": [
        {
            "EvalActionName": "s3:GetObject",
            "EvalResourceName": "arn:aws:s3:::my-data-lake-raw/orders/*",
            "EvalDecision": "allowed"
        }
    ]
}
```

### Check S3 Bucket Policy

```bash
aws s3api get-bucket-policy --bucket my-data-lake-raw --output text | python3 -m json.tool
aws s3api get-public-access-block --bucket my-data-lake-raw
```

### Check Lake Formation Permissions

```bash
aws lakeformation list-permissions \
  --resource '{"Table": {"DatabaseName": "analytics_curated", "Name": "orders"}}'
```

### Check KMS Key Policy

```bash
aws kms get-key-policy --key-id alias/data-lake-key --policy-name default --output text | python3 -m json.tool
```

### IAM Policy Evaluation with Access Analyzer

```bash
aws accessanalyzer list-findings \
  --analyzer-arn arn:aws:access-analyzer:us-east-1:123456789012:analyzer/OrgAnalyzer \
  --filter '{"resourceType":{"eq":["AWS::S3::Bucket"]}}'
```

---

## Advanced Commands

### SCP Deny Check (Organizations)

Access denied may come from an Organization SCP even when IAM allows:

```bash
aws organizations list-policies-for-target \
  --target-id $(aws sts get-caller-identity --query Account --output text) \
  --filter SERVICE_CONTROL_POLICY
```

### S3 Access Denied Debug

```bash
aws s3api head-object --bucket my-bucket --key orders/data.parquet 2>&1
aws s3api get-object-acl --bucket my-bucket --key orders/data.parquet 2>&1
```

### Cross-Account Role Trust

```bash
aws iam get-role --role-name CrossAccountDataAccess \
  --query 'Role.AssumeRolePolicyDocument'
```

---

## Python Boto3 Examples

### Parse AccessDenied Details

```python
from botocore.exceptions import ClientError


def is_access_denied(exc: Exception) -> bool:
    if isinstance(exc, ClientError):
        code = exc.response["Error"]["Code"]
        return code in ("AccessDenied", "AccessDeniedException", "403")
    return False


def log_access_denied(exc: ClientError, context: str) -> None:
    print(f"Access denied [{context}]")
    print(f"  Code: {exc.response['Error']['Code']}")
    print(f"  Message: {exc.response['Error']['Message']}")
    print(f"  RequestId: {exc.response['ResponseMetadata'].get('RequestId')}")
```

### Test Multiple Actions

```python
import boto3

iam = boto3.client("iam")
role_arn = "arn:aws:iam::123456789012:role/GlueETLRole"

actions = ["s3:GetObject", "s3:PutObject", "glue:StartJobRun"]
resources = [
    "arn:aws:s3:::my-data-lake-raw/*",
    "arn:aws:glue:us-east-1:123456789012:job/orders-etl",
]

response = iam.simulate_principal_policy(
    PolicySourceArn=role_arn,
    ActionNames=actions,
    ResourceArns=resources,
)
for result in response["EvaluationResults"]:
    print(result["EvalActionName"], result["EvalDecision"])
```

---

## Security Considerations

- Access denied is working as intended for least privilege — verify intent before widening permissions.
- Use **IAM Access Analyzer** to generate least-privilege policies from CloudTrail activity.
- Deny policies (SCPs, explicit Deny statements) override Allow — check for Deny first.

---

## Troubleshooting

### Decision Tree

```
AccessDenied
├── Wrong account/role? → sts get-caller-identity
├── IAM policy missing action? → simulate-principal-policy
├── Resource policy blocks? → bucket policy / KMS key policy / LF permissions
├── SCP deny? → organizations list-policies-for-target
├── KMS deny? → key policy + iam: kms:Decrypt/Encrypt
└── VPC endpoint policy? → check endpoint policy document
```

### Common Scenarios

| Scenario | Missing Permission | Fix |
|----------|-------------------|-----|
| S3 upload fails | `s3:PutObject` on object ARN | Add `arn:aws:s3:::bucket/prefix/*` |
| S3 list fails | `s3:ListBucket` on bucket ARN | Separate bucket-level permission with prefix condition |
| Athena query fails | LF `SELECT` + `DESCRIBE` | Grant via Lake Formation, not just IAM |
| Glue job fails | `iam:PassRole` on job role | Allow PassRole for specific role ARN |
| KMS encrypt fails | `kms:GenerateDataKey` | Update key policy and IAM policy |
| Cross-account S3 | Bucket policy for external account | Add bucket policy with Principal |
| Lambda invoke denied | Resource-based policy | Add `lambda:InvokeFunction` permission for caller |
| Secrets Manager | `secretsmanager:GetSecretValue` | Scope to secret ARN |

### S3 IAM Policy Pattern

```json
{
  "Effect": "Allow",
  "Action": ["s3:ListBucket"],
  "Resource": "arn:aws:s3:::my-data-lake-raw",
  "Condition": {
    "StringLike": {"s3:prefix": ["orders/*"]}
  }
},
{
  "Effect": "Allow",
  "Action": ["s3:GetObject", "s3:PutObject"],
  "Resource": "arn:aws:s3:::my-data-lake-raw/orders/*"
}
```

---

## Best Practices

- Use **`iam simulate-principal-policy`** before deploying new pipeline roles.
- Grant **Lake Formation permissions** for Athena/Redshift Spectrum — IAM S3 alone is insufficient.
- Apply **prefix-scoped** S3 permissions — never `arn:aws:s3:::*` for pipeline roles.
- Include **`kms:ViaService`** conditions when using SSE-KMS.
- Test access from the **same role** the pipeline uses — not your admin credentials.
- Enable **CloudTrail** data events on sensitive buckets to audit denied calls.
- Document required permissions alongside each pipeline in IaC.
