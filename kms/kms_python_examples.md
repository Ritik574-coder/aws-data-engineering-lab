# KMS — Python Boto3 Examples

## Service Overview

Production **Boto3** patterns for **envelope encryption**, S3 SSE-KMS uploads, Secrets Manager integration, and key lifecycle automation in data engineering pipelines.

**Common scenarios:**
- Encrypt Parquet/CSV files before S3 upload in custom ETL
- Decrypt SSE-KMS S3 objects in Lambda/Glue
- Generate data keys for Spark write operations
- Automate key policy validation in CI/CD

---

## AWS CLI Commands

Validation commands for Python deployment:

```bash
# Verify alias resolves
aws kms describe-key --key-id alias/data-lake-prod --query 'KeyMetadata.KeyState'

# Test encrypt/decrypt round trip
aws kms encrypt --key-id alias/data-lake-prod --plaintext "test" --output text --query CiphertextBlob
```

---

## Advanced Commands

### Generate Data Key Without Plaintext (S3 Only Decrypts)

```bash
aws kms generate-data-key-without-plaintext \
  --key-id alias/data-lake-prod \
  --key-spec AES_256
```

---

## Python (Boto3) Examples

### Basic — Encrypt Small String

```python
import base64

import boto3

kms = boto3.client("kms")

plaintext = b"sensitive-config-value"
resp = kms.encrypt(KeyId="alias/data-lake-prod", Plaintext=plaintext)
ciphertext = resp["CiphertextBlob"]

decrypted = kms.decrypt(CiphertextBlob=ciphertext)["Plaintext"]
assert decrypted == plaintext
```

### Envelope Encryption for Large Files

```python
import logging
import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)


def encrypt_file(input_path: str, output_path: str, key_id: str) -> None:
    """Encrypt a file using KMS-generated data key + AES-GCM."""
    kms = boto3.client("kms")
    input_file = Path(input_path)
    output_file = Path(output_path)

    resp = kms.generate_data_key(KeyId=key_id, KeySpec="AES_256")
    data_key = resp["Plaintext"]
    encrypted_data_key = resp["CiphertextBlob"]

    nonce = os.urandom(12)
    aesgcm = AESGCM(data_key)
    ciphertext = aesgcm.encrypt(nonce, input_file.read_bytes(), None)

    # Format: [4-byte edk length][encrypted data key][12-byte nonce][ciphertext]
    edk_len = len(encrypted_data_key).to_bytes(4, "big")
    output_file.write_bytes(edk_len + encrypted_data_key + nonce + ciphertext)
    logger.info("Encrypted %s → %s", input_path, output_path)


def decrypt_file(input_path: str, output_path: str) -> None:
    kms = boto3.client("kms")
    blob = Path(input_path).read_bytes()

    edk_len = int.from_bytes(blob[:4], "big")
    encrypted_data_key = blob[4 : 4 + edk_len]
    nonce = blob[4 + edk_len : 4 + edk_len + 12]
    ciphertext = blob[4 + edk_len + 12 :]

    data_key = kms.decrypt(CiphertextBlob=encrypted_data_key)["Plaintext"]
    aesgcm = AESGCM(data_key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    Path(output_path).write_bytes(plaintext)
    logger.info("Decrypted %s → %s", input_path, output_path)
```

### Production-Ready — S3 Upload with SSE-KMS

```python
import logging
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def upload_with_kms(
    local_path: str,
    bucket: str,
    key: str,
    kms_key_id: str = "alias/data-lake-prod",
) -> None:
    s3 = boto3.client("s3")
    path = Path(local_path)

    if not path.exists():
        raise FileNotFoundError(local_path)

    try:
        s3.upload_file(
            str(path),
            bucket,
            key,
            ExtraArgs={
                "ServerSideEncryption": "aws:kms",
                "SSEKMSKeyId": kms_key_id,
                "Metadata": {"source": "etl-pipeline", "encrypted": "sse-kms"},
            },
        )
        logger.info("Uploaded s3://%s/%s with SSE-KMS (%s)", bucket, key, kms_key_id)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "AccessDenied":
            logger.error("Check kms:GenerateDataKey on %s for caller role", kms_key_id)
        raise
```

### Download and Verify SSE-KMS Object

```python
import boto3


def download_kms_object(bucket: str, key: str, local_path: str) -> dict:
    s3 = boto3.client("s3")
    resp = s3.get_object(Bucket=bucket, Key=key)
    encryption = resp.get("ServerSideEncryption")
    kms_key = resp.get("SSEKMSKeyId", "N/A")

    with open(local_path, "wb") as f:
        f.write(resp["Body"].read())

    return {"encryption": encryption, "kms_key_id": kms_key}
```

### Create CMK with Rotation Enabled

```python
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def create_data_lake_key(description: str, alias_name: str) -> str:
    kms = boto3.client("kms")
    try:
        resp = kms.create_key(
            Description=description,
            KeyUsage="ENCRYPT_DECRYPT",
            Origin="AWS_KMS",
            Tags=[
                {"TagKey": "Purpose", "TagValue": "data-lake"},
                {"TagKey": "ManagedBy", "TagValue": "data-platform"},
            ],
        )
        key_id = resp["KeyMetadata"]["KeyId"]
        kms.enable_key_rotation(KeyId=key_id)
        kms.create_alias(AliasName=alias_name, TargetKeyId=key_id)
        logger.info("Created key %s with alias %s", key_id, alias_name)
        return key_id
    except ClientError as exc:
        logger.error("Key creation failed: %s", exc.response["Error"]["Message"])
        raise
```

### Create Cross-Account Grant

```python
import boto3


def grant_decrypt_to_role(key_id: str, role_arn: str, grant_name: str) -> str:
    kms = boto3.client("kms")
    resp = kms.create_grant(
        KeyId=key_id,
        GranteePrincipal=role_arn,
        Operations=["Decrypt", "DescribeKey"],
        Name=grant_name,
    )
    return resp["GrantId"]
```

### Re-Encrypt Ciphertext (Key Migration)

```python
import boto3


def migrate_ciphertext(blob: bytes, source_key: str, dest_key: str) -> bytes:
    kms = boto3.client("kms")
    resp = kms.re_encrypt(
        CiphertextBlob=blob,
        SourceKeyId=source_key,
        DestinationKeyId=dest_key,
    )
    return resp["CiphertextBlob"]
```

### Paginate List Keys for Audit

```python
import boto3


def audit_keys() -> list[dict]:
    kms = boto3.client("kms")
    paginator = kms.get_paginator("list_keys")
    keys = []

    for page in paginator.paginate():
        for key in page["Keys"]:
            meta = kms.describe_key(KeyId=key["KeyId"])["KeyMetadata"]
            rotation = False
            try:
                rotation = kms.get_key_rotation_status(KeyId=key["KeyId"])["KeyRotationEnabled"]
            except kms.exceptions.KMSInvalidStateException:
                pass
            keys.append({
                "key_id": meta["KeyId"],
                "arn": meta["Arn"],
                "state": meta["KeyState"],
                "rotation_enabled": rotation,
            })
    return keys
```

### Error Handling Pattern

```python
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def safe_decrypt(ciphertext: bytes) -> bytes | None:
    kms = boto3.client("kms")
    try:
        return kms.decrypt(CiphertextBlob=ciphertext)["Plaintext"]
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "AccessDeniedException":
            logger.error("Caller lacks kms:Decrypt on the source key")
        elif code == "InvalidCiphertextException":
            logger.error("Ciphertext corrupted or wrong key/region")
        raise
```

---

## Security Considerations

- **Zeroize** plaintext data keys from memory after use (`del data_key` in Python; avoid keeping in globals).
- Use **`GenerateDataKeyWithoutPlaintext`** when only S3 needs to decrypt (client-side encryption to S3).
- Never persist plaintext data keys in S3 metadata or logs.
- Scope IAM policies: separate **`kms:CreateGrant`** from day-to-day **`kms:Decrypt`**.
- Validate key policies in CI before deployment to prevent lockout.
- Use **`encryption context`** for additional authenticated data when calling `encrypt`:

```python
kms.encrypt(
    KeyId="alias/data-lake-prod",
    Plaintext=b"token",
    EncryptionContext={"pipeline": "orders-etl", "environment": "prod"},
)
```

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| S3 upload fails with KMS error | Missing `GenerateDataKey` | Update key policy and IAM role |
| `InvalidGrantTokenException` | Expired grant token | Create new grant or use key policy |
| Decrypt returns wrong data | Wrong encryption context | Pass same `EncryptionContext` on decrypt |
| `cryptography` import error | Missing dependency | Add `cryptography` to requirements for envelope encryption |
| Regional mismatch | Key in us-east-1, client in us-west-2 | Instantiate boto3 client in key's region |

---

## Best Practices

- Prefer **SSE-KMS via S3 `ExtraArgs`** over manual envelope encryption unless you control the full crypto path.
- Enable **S3 Bucket Keys** in bucket encryption config to reduce KMS API costs.
- Use **`EncryptionContext`** to bind ciphertext to pipeline name or tenant ID.
- Automate **key rotation status checks** in weekly compliance scripts.
- Store **`CiphertextBlob`** of data keys alongside encrypted artifacts in a consistent binary format.
- Test decrypt from **every consumer role** (Glue, Lambda, Redshift COPY) after policy changes.
- Use **aliases** in code — simplifies CMK rotation without code changes.
- Monitor **`NumberOfRequests`** and **`SecondsUntilKeyMaterialExpiration`** CloudWatch metrics for CMKs.
