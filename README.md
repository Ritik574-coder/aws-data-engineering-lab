# AWS CLI & Boto3 Command Reference

A production-grade reference repository for **Data Engineers**, **Cloud Engineers**, **Analytics Engineers**, and **DevOps Engineers** working with AWS.

This repository covers AWS services commonly used in data engineering workflows through the **AWS CLI v2** and **Python SDK (Boto3)** — with real-world examples, security guidance, troubleshooting, and best practices.

---

## Quick Start

```bash
# Verify AWS CLI v2
aws --version

# Configure credentials (or use SSO / IAM roles)
aws configure

# Verify identity
aws sts get-caller-identity
```

```python
# Verify Boto3
import boto3
print(boto3.__version__)

session = boto3.Session()
print(session.client("sts").get_caller_identity())
```

---

## Repository Structure

| Service | Description | Path |
|---------|-------------|------|
| **S3** | Object storage, data lakes, ETL staging | [s3/](s3/) |
| **IAM** | Identity, access, roles, policies | [iam/](iam/) |
| **EC2** | Compute instances for pipelines | [ec2/](ec2/) |
| **VPC** | Networking, subnets, endpoints | [vpc/](vpc/) |
| **RDS** | Relational databases | [rds/](rds/) |
| **DynamoDB** | NoSQL key-value store | [dynamodb/](dynamodb/) |
| **Lambda** | Serverless compute | [lambda/](lambda/) |
| **Glue** | ETL, crawlers, Data Catalog | [glue/](glue/) |
| **Athena** | Serverless SQL on S3 | [athena/](athena/) |
| **Redshift** | Data warehouse | [redshift/](redshift/) |
| **CloudWatch** | Monitoring, logs, alarms | [cloudwatch/](cloudwatch/) |
| **STS** | Temporary credentials, assume role | [sts/](sts/) |
| **Secrets Manager** | Secret rotation and retrieval | [secrets_manager/](secrets_manager/) |
| **KMS** | Encryption keys | [kms/](kms/) |
| **ECR** | Container registry | [ecr/](ecr/) |
| **ECS** | Container orchestration | [ecs/](ecs/) |
| **EKS** | Managed Kubernetes | [eks/](eks/) |
| **EMR** | Big data processing (Spark, Hive) | [emr/](emr/) |
| **SNS** | Pub/sub notifications | [sns/](sns/) |
| **SQS** | Message queues | [sqs/](sqs/) |
| **EventBridge** | Event bus, scheduling | [eventbridge/](eventbridge/) |
| **Step Functions** | Workflow orchestration | [step_functions/](step_functions/) |
| **Lake Formation** | Data lake governance | [lake_formation/](lake_formation/) |
| **AWS Backup** | Centralized backup | [aws_backup/](aws_backup/) |
| **Organizations** | Multi-account management | [organizations/](organizations/) |
| **Config** | Resource compliance | [config/](config/) |
| **CloudFormation** | Infrastructure as code | [cloudformation/](cloudformation/) |
| **Boto3** | SDK patterns and utilities | [boto3/](boto3/) |
| **Terraform** | CLI + Terraform integration | [terraform_integration/](terraform_integration/) |
| **Troubleshooting** | Common errors and fixes | [troubleshooting/](troubleshooting/) |

---

## Documentation Format

Every service file includes:

1. **Service Overview** — what it does, use cases, when to use it
2. **AWS CLI Commands** — purpose, syntax, parameters, examples, sample output
3. **Advanced Commands** — JMESPath, pagination, filtering, batch ops
4. **Boto3 Examples** — basic, production-ready, error handling, logging
5. **Security Considerations** — least privilege, encryption, credentials
6. **Troubleshooting** — common errors and resolutions
7. **Best Practices** — cost, security, performance, production tips

---

## Data Engineering Use Cases

| Pattern | Services |
|---------|----------|
| Data lake ingestion | S3, Glue, Lake Formation |
| Batch ETL | Glue, EMR, Step Functions |
| Streaming pipelines | Kinesis, Lambda, SQS, EventBridge |
| Ad-hoc analytics | Athena, Redshift |
| Orchestration | Step Functions, EventBridge |
| Secrets & encryption | Secrets Manager, KMS, IAM |
| Monitoring pipelines | CloudWatch, SNS |

---

## Prerequisites

- AWS CLI v2 installed ([installation guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html))
- Python 3.9+ with `boto3` and `botocore`
- Valid AWS credentials (IAM user, SSO, or assumed role)
- Appropriate IAM permissions for the operations documented

---

## Contributing

When adding new commands or examples:

- Use AWS CLI v2 syntax
- Include real-world data engineering context
- Add sample output where helpful
- Document required IAM permissions
- Follow the existing file structure and section headings

---

## License

See [LICENSE](LICENSE).
