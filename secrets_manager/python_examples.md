# Secrets Manager — Python Boto3 Examples

## Service Overview

Production **Boto3** patterns for retrieving, caching, and rotating secrets in data engineering pipelines — Glue jobs, Lambda functions, Airflow operators, and custom ETL scripts.

**Typical integration points:**
- Glue `getSecret` via connection or direct SDK call
- Lambda environment variable holding **secret ARN** (not the secret value)
- Airflow `AwsSecretsManagerBackend` for variable storage
- Redshift Data API `SecretArn` parameter

---

## AWS CLI Commands

Quick validation before deploying Python jobs:

```bash
# Verify secret exists and is readable
aws secretsmanager get-secret-value --secret-id redshift/etl-service --query 'Name' --output text

# Check rotation status
aws secretsmanager describe-secret --secret-id rds/analytics-metadata --query 'RotationEnabled'
```

---

## Advanced Commands

### Create Secret from File (JSON)

```bash
aws secretsmanager create-secret \
  --name glue/snowflake-ingestion \
  --secret-string file://snowflake-creds.json
```

### Rotate Immediately (On-Demand)

```bash
aws secretsmanager rotate-secret --secret-id rds/analytics-metadata --rotate-immediately
```

---

## Python (Boto3) Examples

### Basic — Parse JSON Secret

```python
import json

import boto3


def get_secret(secret_id: str, region: str = "us-east-1") -> dict:
    client = boto3.client("secretsmanager", region_name=region)
    resp = client.get_secret_value(SecretId=secret_id)
    return json.loads(resp["SecretString"])


creds = get_secret("redshift/etl-service")
connection_url = (
    f"redshift://{creds['username']}:{creds['password']}"
    f"@{creds['host']}:{creds['port']}/{creds['dbname']}"
)
```

### Production-Ready — Cached Secret with TTL

```python
import json
import logging
import time
from functools import lru_cache
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[float, dict[str, Any]]] = {}
DEFAULT_TTL = 300  # 5 minutes — balance rotation vs API calls


def get_secret_cached(secret_id: str, ttl: int = DEFAULT_TTL) -> dict[str, Any]:
    now = time.time()
    cached = _cache.get(secret_id)
    if cached and (now - cached[0]) < ttl:
        return cached[1]

    client = boto3.client("secretsmanager")
    try:
        resp = client.get_secret_value(SecretId=secret_id)
        value = json.loads(resp["SecretString"])
        _cache[secret_id] = (now, value)
        logger.debug("Fetched secret %s (version %s)", secret_id, resp.get("VersionId"))
        return value
    except ClientError as exc:
        logger.error("Failed to get secret %s: %s", secret_id, exc.response["Error"]["Message"])
        raise
```

### Create Secret Programmatically

```python
import json
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def create_db_secret(
    name: str,
    username: str,
    password: str,
    host: str,
    port: int,
    dbname: str,
    engine: str = "redshift",
) -> str:
    client = boto3.client("secretsmanager")
    secret_value = {
        "username": username,
        "password": password,
        "host": host,
        "port": port,
        "dbname": dbname,
        "engine": engine,
    }
    try:
        resp = client.create_secret(
            Name=name,
            SecretString=json.dumps(secret_value),
            Tags=[
                {"Key": "ManagedBy", "Value": "data-platform"},
                {"Key": "Engine", "Value": engine},
            ],
        )
        logger.info("Created secret %s", resp["ARN"])
        return resp["ARN"]
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ResourceExistsException":
            client.update_secret(SecretId=name, SecretString=json.dumps(secret_value))
            logger.info("Updated existing secret %s", name)
            return name
        raise
```

### Glue Job — Redshift Connection Helper

```python
import json
import sys

import boto3


def get_redshift_jdbc_props(secret_arn: str) -> dict:
    """Use in Glue shell/Python jobs with --SECRET_ARN job parameter."""
    client = boto3.client("secretsmanager")
    resp = client.get_secret_value(SecretId=secret_arn)
    creds = json.loads(resp["SecretString"])
    jdbc_url = (
        f"jdbc:redshift://{creds['host']}:{creds['port']}/{creds['dbname']}"
    )
    return {
        "url": jdbc_url,
        "user": creds["username"],
        "password": creds["password"],
    }


if __name__ == "__main__":
    secret_arn = sys.argv[1]  # passed from Glue job parameters
    props = get_redshift_jdbc_props(secret_arn)
    # Use props with spark.read.format("jdbc").options(**props)...
```

### Lambda Rotation Handler (Custom — API Key)

```python
import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)
secrets_client = boto3.client("secretsmanager")


def lambda_handler(event, context):
    """Skeleton for rotating a third-party API key secret."""
    secret_arn = event["SecretId"]
    token = event["ClientRequestToken"]
    step = event["Step"]

    if step == "createSecret":
        current = secrets_client.get_secret_value(SecretId=secret_arn, VersionStage="AWSCURRENT")
        pending = json.loads(current["SecretString"])
        pending["api_key"] = _fetch_new_api_key_from_provider()
        secrets_client.put_secret_value(
            SecretId=secret_arn,
            ClientRequestToken=token,
            SecretString=json.dumps(pending),
            VersionStages=["AWSPENDING"],
        )
    elif step == "setSecret":
        pending = secrets_client.get_secret_value(SecretId=secret_arn, VersionStage="AWSPENDING")
        _validate_api_key(json.loads(pending["SecretString"])["api_key"])
    elif step == "testSecret":
        pending = secrets_client.get_secret_value(SecretId=secret_arn, VersionStage="AWSPENDING")
        _test_api_connectivity(json.loads(pending["SecretString"])["api_key"])
    elif step == "finishSecret":
        secrets_client.update_secret_version_stage(
            SecretId=secret_arn,
            VersionStage="AWSCURRENT",
            MoveToVersionId=token,
            RemoveFromVersionId=secrets_client.describe_secret(SecretId=secret_arn)["VersionIdsToStages"],
        )
    return {"statusCode": 200}


def _fetch_new_api_key_from_provider() -> str:
    raise NotImplementedError

def _validate_api_key(key: str) -> None:
    pass

def _test_api_connectivity(key: str) -> None:
    pass
```

### Paginate All Secrets for Audit

```python
import boto3


def list_all_secrets(name_prefix: str | None = None) -> list[dict]:
    client = boto3.client("secretsmanager")
    paginator = client.get_paginator("list_secrets")
    secrets = []

    for page in paginator.paginate():
        for secret in page["SecretList"]:
            if name_prefix and not secret["Name"].startswith(name_prefix):
                continue
            secrets.append({
                "name": secret["Name"],
                "arn": secret["ARN"],
                "rotation_enabled": secret.get("RotationEnabled", False),
                "last_changed": str(secret.get("LastChangedDate", "")),
            })
    return secrets
```

### Error Handling with Fallback Stage

```python
import json
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def get_secret_with_version(secret_id: str, version_stage: str = "AWSCURRENT") -> dict:
    client = boto3.client("secretsmanager")
    try:
        resp = client.get_secret_value(SecretId=secret_id, VersionStage=version_stage)
        return json.loads(resp["SecretString"])
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "ResourceNotFoundException":
            logger.error("Secret %s not found", secret_id)
        elif code == "AccessDeniedException":
            logger.error("Insufficient permissions for %s", secret_id)
        raise
```

---

## Security Considerations

- Pass **secret ARN** to Lambda/Glue via environment or job parameters — never the secret value.
- Implement **cache TTL ≤ rotation interval** to pick up rotated credentials.
- Clear in-memory caches after rotation events (SNS/EventBridge trigger).
- Restrict **`secretsmanager:PutSecretValue`** to rotation Lambdas and break-glass admin roles only.
- Use **`aws:SourceAccount`** and **`aws:SourceArn`** condition keys in resource policies.
- Avoid logging secret values — log secret **name/ARN** and **version ID** only.

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `json.JSONDecodeError` | Secret is plain string, not JSON | Standardize on JSON or handle plain text |
| Cached stale password after rotation | TTL too long | Reduce TTL; listen for rotation events |
| `DecryptionFailure` | KMS key policy deny | Grant `kms:Decrypt` to caller role on CMK |
| Glue connection test fails | Wrong JDBC format in secret | Include `engine`, `host`, `port`, `dbname` keys |
| Lambda timeout on cold start + secret fetch | VPC + NAT latency | Increase timeout; use VPC endpoint for Secrets Manager |

---

## Best Practices

- Standardize secret JSON schema across **RDS, Redshift, and custom APIs**.
- Use **`@lru_cache` with TTL wrapper** or external cache (Redis) for high-frequency reads.
- Wire rotation failures to **SNS/CloudWatch alarms**.
- In Airflow, use **`SecretsManagerBackend`** instead of storing connections in metadata DB.
- Run periodic **audit scripts** (`list_secrets`) to find orphans and non-rotated secrets.
- For local dev, use **`AWS_PROFILE`** with SSO — never copy prod secrets locally.
- Combine with **Parameter Store** for non-sensitive config (bucket names, table prefixes).
