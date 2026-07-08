# AWS CLI with Terraform

## Service Overview

Terraform and the AWS CLI complement each other in data platform workflows. Terraform manages declarative infrastructure state; the AWS CLI handles ad-hoc operations, debugging, data migration, and tasks Terraform does not cover.

**Common integration patterns:**
- Use CLI to verify resources Terraform created (`aws sts get-caller-identity`, `aws s3 ls`)
- Import existing resources into Terraform state
- Run CLI commands in `local-exec` / `remote-exec` provisioners
- Share AWS profile/credential configuration between both tools

**When to use CLI vs Terraform:** Terraform for repeatable infrastructure; CLI for one-off ops, troubleshooting, and pipeline runtime tasks.

---

## AWS CLI Commands

### Verify Terraform Deploy Identity

```bash
# Same profile Terraform uses
export AWS_PROFILE=data-engineer
export AWS_DEFAULT_REGION=us-east-1

aws sts get-caller-identity
terraform plan
```

### Inspect Terraform-Managed Resources

```bash
# After terraform apply
aws s3 ls | grep data-lake
aws glue get-databases --query 'DatabaseList[*].Name'
aws iam get-role --role-name glue-etl-role
```

### Import Existing Resource to Terraform

```bash
# Discover resource ID via CLI
aws s3api head-bucket --bucket my-existing-data-lake-raw

# Import into Terraform state
terraform import aws_s3_bucket.raw my-existing-data-lake-raw
```

### S3 Backend Bootstrap

```bash
# Create state bucket (one-time, often via CLI before Terraform backend config)
aws s3api create-bucket \
  --bucket my-terraform-state-123456789012 \
  --region us-east-1

aws s3api put-bucket-versioning \
  --bucket my-terraform-state-123456789012 \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket my-terraform-state-123456789012 \
  --server-side-encryption-configuration '{
    "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "aws:kms"}}]
  }'

aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

---

## Advanced Commands

### Terraform Provider Environment Variables

```bash
export AWS_PROFILE=data-engineer
export AWS_DEFAULT_REGION=us-east-1
export AWS_SDK_LOAD_CONFIG=1          # Required for SSO profiles
export TF_VAR_environment=production

terraform init -backend-config="bucket=my-terraform-state-123456789012"
terraform plan -var-file=environments/production.tfvars
terraform apply -auto-approve
```

### Local-Exec Provisioner Pattern

```hcl
resource "aws_glue_job" "orders_etl" {
  name     = "orders-etl"
  role_arn = aws_iam_role.glue.arn
  # ...

  provisioner "local-exec" {
    command = "aws glue start-job-run --job-name ${self.name} --arguments '{\"--date\":\"init\"}'"
    environment = {
      AWS_PROFILE = "data-engineer"
    }
  }
}
```

**Caution:** Prefer EventBridge or Step Functions over provisioners for production triggers.

### External Data Source via CLI

```hcl
data "external" "caller_identity" {
  program = ["bash", "-c", "aws sts get-caller-identity --output json"]
}

output "account_id" {
  value = data.external.caller_identity.result.Account
}
```

### Compare Terraform State vs Actual (Drift)

```bash
# Terraform drift detection
terraform plan -detailed-exitcode

# AWS-native drift (CloudFormation stacks)
aws cloudformation detect-stack-drift --stack-name data-lake-foundation

# Manual CLI check
terraform output raw_bucket_name
aws s3api get-bucket-encryption --bucket $(terraform output -raw raw_bucket_name)
```

### Assume Role for Multi-Account Terraform

`~/.aws/config`:

```ini
[profile terraform-prod]
role_arn = arn:aws:iam::987654321098:role/TerraformDeployRole
source_profile = data-engineer-sso
region = us-east-1
```

```bash
export AWS_PROFILE=terraform-prod
terraform apply
```

Terraform provider configuration:

```hcl
provider "aws" {
  profile = "terraform-prod"
  region  = "us-east-1"

  default_tags {
    tags = {
      ManagedBy   = "terraform"
      Environment = var.environment
    }
  }
}
```

---

## Python Boto3 Examples

### Post-Terraform Validation Script

```python
import json
import subprocess
import boto3


def get_terraform_output(key: str) -> str:
    result = subprocess.run(
        ["terraform", "output", "-raw", key],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def validate_data_lake():
    bucket = get_terraform_output("raw_bucket_name")
    s3 = boto3.client("s3")

    encryption = s3.get_bucket_encryption(Bucket=bucket)
    assert encryption["ServerSideEncryptionConfiguration"]

    public_block = s3.get_public_access_block(Bucket=bucket)
    config = public_block["PublicAccessBlockConfiguration"]
    assert all(config.values()), "Public access block not fully enabled"

    print(f"Validation passed for s3://{bucket}")


if __name__ == "__main__":
    validate_data_lake()
```

---

## Security Considerations

- Store **Terraform state** in encrypted S3 with versioning and DynamoDB locking.
- Use **separate IAM roles** for Terraform deploy vs runtime pipeline execution.
- Never commit `.tfstate` files — state contains sensitive resource attributes.
- Scope Terraform role with least privilege; use `iam:PassRole` conditions.
- Enable **CloudTrail** for Terraform API calls to detect unauthorized changes.
- Use **OIDC** (GitHub Actions, GitLab) for CI/CD Terraform — no long-lived keys.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| Terraform auth fails, CLI works | Missing `AWS_SDK_LOAD_CONFIG=1` for SSO | Export variable before `terraform plan` |
| `Error acquiring state lock` | Stale DynamoDB lock | `terraform force-unlock <lock-id>` after verifying no running apply |
| Import fails | Wrong resource ID format | Use CLI to get exact ID/ARN |
| Provider version mismatch | Lock file out of date | Run `terraform init -upgrade` |
| `AccessDenied` on apply | Terraform role missing permission | Compare failed action in error with IAM policy |
| Local-exec provisioner fails | Different env than shell | Pass `environment` block with AWS vars |

---

## Best Practices

- **Single credential source** — same AWS profile for CLI and Terraform locally.
- **Bootstrap state backend** with CLI once; manage everything else in Terraform.
- **Use `-var-file` per environment** — never hardcode account-specific values.
- **Run `terraform plan` in CI** on every PR; require review for IAM changes.
- **Validate with CLI** after apply — spot-check encryption, public access, tags.
- **Avoid local-exec provisioners** for critical path — use proper orchestration.
- **Pin provider versions** in `required_providers` block.
- **Use `terraform output`** to feed pipeline configuration rather than hardcoding ARNs.
- **Document manual CLI steps** that cannot be automated in runbooks alongside Terraform code.
