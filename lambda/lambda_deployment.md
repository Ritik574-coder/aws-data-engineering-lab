# Lambda — Deployment

## Service Overview

Lambda deployment covers packaging code, uploading artifacts, creating/updating functions, managing layers, and configuring event sources. Data engineering teams typically deploy via CI/CD (GitHub Actions, CodePipeline) using S3-based packages or container images for heavier dependencies (Pandas, PyArrow).

**Common use cases:**
- Deploy S3-triggered validation Lambdas on every Git merge
- Ship shared dependency layers (boto3, pandas, awswrangler) across pipeline functions
- Container-based Lambda for ML inference or large Python dependencies
- Blue/green deployments using versions and aliases

**When to use it:** As part of automated pipeline releases — not for one-off Console edits in production accounts.

---

## AWS CLI Commands

### Create Deployment Package (Local)

**Purpose:** Zip handler and dependencies before upload.

**Command:**

```bash
cd lambda/s3-landing-validator
pip install -r requirements.txt -t package/
cp handler.py package/
cd package && zip -r ../deployment.zip . && cd ..
```

---

### Create Function (Zip Package)

**Purpose:** Deploy a new Lambda from a local zip artifact.

**Command:**

```bash
aws lambda create-function \
  --function-name s3-landing-validator \
  --runtime python3.12 \
  --role arn:aws:iam::123456789012:role/LambdaS3ValidatorRole \
  --handler handler.lambda_handler \
  --zip-file fileb://deployment.zip \
  --timeout 120 \
  --memory-size 512 \
  --environment 'Variables={LOG_LEVEL=INFO,GLUE_JOB_NAME=orders-daily-etl}' \
  --tags Environment=prod,Team=data-platform
```

**Example Output (abbreviated):**

```json
{
    "FunctionName": "s3-landing-validator",
    "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:s3-landing-validator",
    "Runtime": "python3.12",
    "State": "Pending",
    "LastUpdateStatus": "InProgress"
}
```

---

### Update Function Code

**Purpose:** Push a new zip without changing configuration.

**Command:**

```bash
aws lambda update-function-code \
  --function-name s3-landing-validator \
  --zip-file fileb://deployment.zip
```

**Example Output:**

```json
{
    "FunctionName": "s3-landing-validator",
    "LastUpdateStatus": "InProgress",
    "CodeSha256": "abc123...",
    "CodeSize": 15234567
}
```

---

### Deploy via S3 (Large Packages > 50 MB direct upload)

**Purpose:** Upload zip to S3 first, then reference from Lambda (required for large artifacts).

**Command:**

```bash
aws s3 cp deployment.zip s3://etl-artifacts/lambda/s3-landing-validator/deployment.zip

aws lambda update-function-code \
  --function-name s3-landing-validator \
  --s3-bucket etl-artifacts \
  --s3-key lambda/s3-landing-validator/deployment.zip
```

**Example Output:**

```json
{
    "FunctionName": "s3-landing-validator",
    "CodeSize": 52428800,
    "LastUpdateStatus": "InProgress"
}
```

---

### Wait for Update to Complete

**Purpose:** Block CI/CD until the function is ready.

**Command:**

```bash
aws lambda wait function-updated --function-name s3-landing-validator
aws lambda get-function --function-name s3-landing-validator \
  --query 'Configuration.{State:State,LastUpdateStatus:LastUpdateStatus}' \
  --output table
```

**Example Output:**

```
---------------------------------
|         GetFunction           |
+------------------+------------+
| LastUpdateStatus |   State    |
+------------------+------------+
|  Successful      |  Active    |
+------------------+------------+
```

---

### Create Lambda Layer

**Purpose:** Share common dependencies across multiple functions.

**Command:**

```bash
mkdir -p layer/python
pip install awswrangler pandas -t layer/python/
cd layer && zip -r ../awswrangler-layer.zip python && cd ..

aws lambda publish-layer-version \
  --layer-name data-engineering-deps \
  --description "awswrangler + pandas for data pipelines" \
  --zip-file fileb://awswrangler-layer.zip \
  --compatible-runtimes python3.11 python3.12
```

**Example Output:**

```json
{
    "LayerArn": "arn:aws:lambda:us-east-1:123456789012:layer:data-engineering-deps",
    "LayerVersionArn": "arn:aws:lambda:us-east-1:123456789012:layer:data-engineering-deps:3",
    "Version": 3
}
```

---

### Attach Layer to Function

**Purpose:** Reference a published layer version in a function.

**Command:**

```bash
aws lambda update-function-configuration \
  --function-name s3-landing-validator \
  --layers arn:aws:lambda:us-east-1:123456789012:layer:data-engineering-deps:3
```

---

### Deploy Container Image Function

**Purpose:** Deploy Lambda from ECR (for heavy dependencies).

**Command:**

```bash
aws lambda create-function \
  --function-name parquet-compactor \
  --package-type Image \
  --code ImageUri=123456789012.dkr.ecr.us-east-1.amazonaws.com/parquet-compactor:latest \
  --role arn:aws:iam::123456789012:role/LambdaCompactorRole \
  --timeout 900 \
  --memory-size 2048 \
  --architectures arm64
```

---

### Create Event Source Mapping (SQS)

**Purpose:** Wire an SQS queue as a Lambda trigger.

**Command:**

```bash
aws lambda create-event-source-mapping \
  --function-name s3-landing-validator \
  --event-source-arn arn:aws:sqs:us-east-1:123456789012:landing-file-queue \
  --batch-size 10 \
  --maximum-batching-window-in-seconds 5 \
  --function-response-types ReportBatchItemFailures
```

**Example Output:**

```json
{
    "UUID": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "State": "Creating",
    "BatchSize": 10
}
```

---

## Advanced Commands

### Publish Version and Update Alias (Blue/Green)

```bash
VERSION=$(aws lambda publish-version --function-name s3-landing-validator --query Version --output text)

aws lambda update-alias \
  --function-name s3-landing-validator \
  --name prod \
  --function-version "$VERSION"
```

### Code Signing Configuration

```bash
aws lambda update-function-code-signing-config \
  --function-name s3-landing-validator \
  --code-signing-config-arn arn:aws:lambda:us-east-1:123456789012:code-signing-config:prod
```

### Compare Code SHA Between Versions

```bash
aws lambda list-versions-by-function --function-name s3-landing-validator \
  --query 'Versions[].{Version:Version,Sha:CodeSha256,Modified:LastModified}' \
  --output table
```

### SAM/CloudFormation Deploy (reference)

```bash
sam build && sam deploy --guided
# Or
aws cloudformation deploy \
  --template-file template.yaml \
  --stack-name orders-ingest-lambda \
  --capabilities CAPABILITY_IAM
```

---

## Python Boto3 Examples

### Basic — Update Function Code from Bytes

```python
from pathlib import Path

import boto3

zip_bytes = Path("deployment.zip").read_bytes()
client = boto3.client("lambda")

response = client.update_function_code(
    FunctionName="s3-landing-validator",
    ZipFile=zip_bytes,
)
print(response["LastUpdateStatus"])
```

### Production-Ready — S3-Based Deploy with Waiter

```python
import logging
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def deploy_lambda_from_s3(
    function_name: str,
    local_zip: str,
    artifact_bucket: str,
    artifact_key: str,
) -> None:
    s3 = boto3.client("s3")
    lam = boto3.client("lambda")

    zip_path = Path(local_zip)
    if not zip_path.exists():
        raise FileNotFoundError(local_zip)

    logger.info("Uploading %s to s3://%s/%s", local_zip, artifact_bucket, artifact_key)
    s3.upload_file(str(zip_path), artifact_bucket, artifact_key)

    lam.update_function_code(
        FunctionName=function_name,
        S3Bucket=artifact_bucket,
        S3Key=artifact_key,
    )

    waiter = lam.get_waiter("function_updated")
    waiter.wait(FunctionName=function_name)
    logger.info("Function %s updated successfully", function_name)
```

### Publish Layer and Attach

```python
import boto3


def publish_and_attach_layer(function_name: str, layer_zip: str, layer_name: str) -> str:
    lam = boto3.client("lambda")

    with open(layer_zip, "rb") as f:
        layer_resp = lam.publish_layer_version(
            LayerName=layer_name,
            ZipFile=f.read(),
            CompatibleRuntimes=["python3.12"],
        )

    layer_arn = layer_resp["LayerVersionArn"]
    config = lam.get_function_configuration(FunctionName=function_name)
    existing_layers = [l["Arn"] for l in config.get("Layers", [])]
    existing_layers = [a for a in existing_layers if layer_name not in a]
    existing_layers.append(layer_arn)

    lam.update_function_configuration(FunctionName=function_name, Layers=existing_layers)
    lam.get_waiter("function_updated").wait(FunctionName=function_name)
    return layer_arn
```

---

## Security Considerations

- Store deployment artifacts in a **private S3 bucket** with SSE-KMS; restrict `s3:GetObject` to CI/CD roles.
- Use **IAM deployment roles** separate from runtime roles — CI can update code; runtime cannot.
- Enable **code signing** for production functions to verify package integrity.
- Scan container images with **ECR image scanning** before Lambda deploy.
- Never commit **`.env`** or credentials into deployment zips.
- Pin dependency versions in `requirements.txt` to prevent supply-chain drift.

---

## Troubleshooting

| Error / Symptom | Root Cause | Resolution |
|-----------------|------------|------------|
| `RequestEntityTooLargeException` | Zip > 50 MB direct limit | Upload to S3; use `--s3-bucket`/`--s3-key` |
| `ResourceConflictException` | Update in progress | Wait with `function-updated` waiter |
| `InvalidParameterValueException` | Handler path wrong | Match `--handler` to module.function in zip root |
| Layer import fails | Wrong folder structure | Layer must be `python/lib/python3.12/site-packages/` |
| `Unzipped size must be smaller than` | Too many deps | Split into layers or use container image |
| Stale code after deploy | Invoking `$LATEST` during update | Publish version; route alias after successful deploy |

---

## Best Practices

- Deploy via **CI/CD** with immutable S3 artifact paths (`s3://.../lambda/name/<git-sha>.zip`).
- Use **`aws lambda wait function-updated`** before running integration tests.
- Split **heavy deps into layers** shared across pipeline functions.
- Prefer **container images** when dependencies exceed layer size limits or need OS packages.
- Implement **blue/green** with aliases — never point production traffic to `$LATEST`.
- Keep deployment packages **minimal** — exclude tests, docs, and `.pyc` files from zip.
- Version **layer ARNs** explicitly in IaC; avoid `:latest` layer references.
- Run **`pip install --platform manylinux2014_x86_64 --only-binary=:all:`** when building on Mac for Lambda Linux.
