# CloudFormation — Stack Management

## Service Overview

**AWS CloudFormation** provides infrastructure as code (IaC) for provisioning and managing AWS resources via templates. Stacks are declarative, versioned, and support change sets for safe updates.

**Common use cases:**
- Deploy data lake S3 buckets, Glue databases, and IAM roles as a unit
- Version-controlled pipeline infrastructure (Lambda, Step Functions, EventBridge)
- Cross-stack references for shared VPC and security group exports
- Drift detection for production data platform resources

**When to use it:** When you need repeatable, auditable infrastructure deployments with rollback support — complementary to Terraform for AWS-native workflows and StackSets for multi-account rollout.

---

## AWS CLI Commands

### Validate Template

**Purpose:** Check template syntax before deployment.

**Command:**

```bash
aws cloudformation validate-template --template-body file://data-lake-stack.yaml
```

**With S3 template:**

```bash
aws cloudformation validate-template \
  --template-url https://my-templates.s3.amazonaws.com/data-lake-stack.yaml
```

---

### Create Stack

**Purpose:** Deploy a data lake foundation stack.

**Command:**

```bash
aws cloudformation create-stack \
  --stack-name data-lake-foundation \
  --template-body file://data-lake-stack.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=production \
    ParameterKey=RawBucketName,ParameterValue=my-data-lake-raw \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags Key=Team,Value=DataEngineering Key=Environment,Value=production \
  --on-failure ROLLBACK
```

**Parameters:**
| Flag | Description |
|------|-------------|
| `--capabilities` | Required when template creates IAM resources |
| `--on-failure` | `ROLLBACK`, `DELETE`, or `DO_NOTHING` |
| `--disable-rollback` | Keep failed resources for debugging |

---

### Describe Stack Events

**Purpose:** Monitor deployment progress and diagnose failures.

**Command:**

```bash
aws cloudformation describe-stack-events \
  --stack-name data-lake-foundation \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
  --output table
```

---

### Describe Stacks

```bash
aws cloudformation describe-stacks --stack-name data-lake-foundation
```

**Example Output (truncated):**

```json
{
    "Stacks": [{
        "StackName": "data-lake-foundation",
        "StackStatus": "CREATE_COMPLETE",
        "CreationTime": "2025-01-15T10:00:00+00:00",
        "Outputs": [
            {"OutputKey": "RawBucketArn", "OutputValue": "arn:aws:s3:::my-data-lake-raw"}
        ]
    }]
}
```

---

### Update Stack

```bash
aws cloudformation update-stack \
  --stack-name data-lake-foundation \
  --template-body file://data-lake-stack-v2.yaml \
  --parameters ParameterKey=Environment,ParameterValue=production \
  --capabilities CAPABILITY_NAMED_IAM
```

---

### Create Change Set

**Purpose:** Preview changes before applying an update.

**Command:**

```bash
aws cloudformation create-change-set \
  --stack-name data-lake-foundation \
  --change-set-name add-curated-bucket-v1 \
  --template-body file://data-lake-stack-v2.yaml \
  --capabilities CAPABILITY_NAMED_IAM

aws cloudformation describe-change-set \
  --stack-name data-lake-foundation \
  --change-set-name add-curated-bucket-v1

aws cloudformation execute-change-set \
  --stack-name data-lake-foundation \
  --change-set-name add-curated-bucket-v1
```

---

### List Stack Resources

```bash
aws cloudformation list-stack-resources --stack-name data-lake-foundation
```

---

### Delete Stack

```bash
aws cloudformation delete-stack --stack-name data-lake-foundation
```

**Note:** S3 buckets with objects may block deletion unless template uses `DeletionPolicy: Retain` or bucket is emptied.

---

### Detect Stack Drift

```bash
aws cloudformation detect-stack-drift --stack-name data-lake-foundation
aws cloudformation describe-stack-drift-detection-status --stack-drift-detection-id <id>
aws cloudformation describe-stack-resource-drifts --stack-name data-lake-foundation
```

---

## Advanced Commands

### Sample Template Snippet — S3 Data Lake Bucket

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Description: Data lake raw zone bucket

Parameters:
  Environment:
    Type: String
    AllowedValues: [dev, staging, production]

Resources:
  RawBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub "my-data-lake-raw-${Environment}"
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: aws:kms
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
      Tags:
        - Key: Environment
          Value: !Ref Environment

Outputs:
  RawBucketArn:
    Value: !GetAtt RawBucket.Arn
    Export:
      Name: !Sub "${AWS::StackName}-RawBucketArn"
```

### StackSets (Multi-Account)

```bash
aws cloudformation create-stack-set \
  --stack-set-name data-lake-guardrails \
  --template-body file://guardrails.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --permission-model SERVICE_MANAGED \
  --auto-deployment Enabled=true,RetainStacksOnAccountRemoval=false
```

### Export/Import Values

```bash
aws cloudformation list-exports \
  --query 'Exports[?Name==`data-lake-foundation-RawBucketArn`]'
```

### Package Template (Lambda + Assets)

```bash
aws cloudformation package \
  --template-file template.yaml \
  --s3-bucket my-cfn-artifacts \
  --output-template-file packaged.yaml

aws cloudformation deploy \
  --template-file packaged.yaml \
  --stack-name etl-pipeline \
  --capabilities CAPABILITY_IAM
```

---

## Python Boto3 Examples

See [cloudformation_python_examples.md](cloudformation_python_examples.md).

---

## Security Considerations

- Never embed secrets in templates — use **SSM Parameter Store** or **Secrets Manager** dynamic references.
- Require `CAPABILITY_IAM` approval in CI/CD pipelines — review IAM changes in change sets.
- Use **stack policies** to prevent accidental updates/deletion of production stacks.
- Enable **termination protection** on production stacks: `UpdateTerminationProtection`.
- Scope CloudFormation service role with least privilege for resource creation.
- Store templates in version-controlled repositories with PR review.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `ValidationError` | Template syntax or unsupported property | Run `validate-template`; check resource docs |
| `AlreadyExistsException` | Stack name in use | Delete old stack or use unique name |
| `No updates are to be performed` | Template identical to deployed | Modify template or parameters |
| `ROLLBACK_COMPLETE` | Create failed and rolled back | Check `describe-stack-events` for failed resource |
| S3 bucket delete fails | Bucket not empty | Empty bucket or set `DeletionPolicy: Retain` |
| `InsufficientCapabilities` | IAM resource without capability flag | Add `CAPABILITY_NAMED_IAM` or `CAPABILITY_IAM` |

---

## Best Practices

- **Use change sets** for all production updates — never blind `update-stack`.
- **Parameterize environments** — one template, different parameter files per env.
- **Export stable outputs** — bucket ARNs, role ARNs for cross-stack references.
- **Set DeletionPolicy: Retain** on stateful resources (S3, RDS) in production.
- **Enable termination protection** and stack policies on critical stacks.
- **Detect drift regularly** — reconcile manual console changes back to IaC.
- **Use nested stacks** for large data platform templates — modularize by domain.
- **Tag all resources** via `Tags` property or stack-level tags for cost tracking.
