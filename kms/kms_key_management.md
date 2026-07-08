# KMS — Key Management

## Service Overview

**AWS Key Management Service (KMS)** creates and manages cryptographic keys for encrypting data across AWS data services. It is foundational for securing data lakes, databases, secrets, and ETL artifacts.

**Common use cases in data engineering:**
- **SSE-KMS** encryption on S3 data lake buckets (raw, curated, exports)
- Encrypting **Redshift**, **RDS**, and **EBS** volumes at rest
- Encrypting **Secrets Manager** secrets and **SSM Parameter Store** SecureStrings
- **Envelope encryption** for large files in custom pipelines
- Cross-account data sharing with **grant-based** or **key policy** access

**Key types:**
| Type | Description |
|------|-------------|
| **AWS managed** | Service-owned (e.g., `aws/s3`); free, limited control |
| **Customer managed (CMK)** | Full policy control, rotation, aliases, audit |
| **AWS owned** | Shared across accounts; not visible in your account |

**When to use CMK:** When you need granular IAM policies, CloudTrail audit of key usage, cross-account access, or automatic annual rotation.

---

## AWS CLI Commands

### List Keys and Aliases

**Purpose:** Inventory encryption keys for governance.

**Command:**

```bash
aws kms list-keys --query 'Keys[].KeyId' --output table

aws kms list-aliases \
  --query 'Aliases[?contains(AliasName, `data-lake`)].{Alias:AliasName,KeyId:TargetKeyId}' \
  --output table
```

---

### Create Customer Managed Key

**Purpose:** Create a CMK for S3 data lake encryption.

**Command:**

```bash
aws kms create-key \
  --description "Data lake S3 encryption key - prod" \
  --key-usage ENCRYPT_DECRYPT \
  --origin AWS_KMS \
  --tags TagKey=Environment,TagValue=prod TagKey=Team,TagValue=data-platform
```

**Example Output:**

```json
{
    "KeyMetadata": {
        "KeyId": "12345678-1234-1234-1234-123456789012",
        "Arn": "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012",
        "Enabled": true,
        "KeyState": "Enabled"
    }
}
```

---

### Create Alias

**Purpose:** Human-readable reference for policies and S3 bucket defaults.

**Command:**

```bash
aws kms create-alias \
  --alias-name alias/data-lake-prod \
  --target-key-id 12345678-1234-1234-1234-123456789012
```

---

### Describe Key

**Command:**

```bash
aws kms describe-key \
  --key-id alias/data-lake-prod \
  --query 'KeyMetadata.{Id:KeyId,Arn:Arn,State:KeyState,Rotation:KeyRotationStatus,Spec:KeySpec}' \
  --output table
```

---

### Enable Automatic Key Rotation

**Purpose:** Rotate CMK material annually (AWS-managed process).

**Command:**

```bash
aws kms enable-key-rotation --key-id alias/data-lake-prod
```

---

### Encrypt and Decrypt (Small Payloads)

**Purpose:** Encrypt connection strings, tokens, or PII tokens (< 4 KB).

**Command:**

```bash
# Encrypt
CIPHER=$(aws kms encrypt \
  --key-id alias/data-lake-prod \
  --plaintext "sensitive-pipeline-token" \
  --query 'CiphertextBlob' --output text)

# Decrypt
aws kms decrypt \
  --ciphertext-blob "$CIPHER" \
  --query 'Plaintext' --output text | base64 -d
```

---

### Generate Data Key (Envelope Encryption)

**Purpose:** Generate AES-256 data key for encrypting large S3 objects locally.

**Command:**

```bash
aws kms generate-data-key \
  --key-id alias/data-lake-prod \
  --key-spec AES_256 \
  --query '{Plaintext:Plaintext,CiphertextBlob:CiphertextBlob}' \
  --output json
```

**Explanation:** Use `Plaintext` to encrypt data locally; store `CiphertextBlob` alongside the object for decryption.

---

### Create Grant for Cross-Account Role

**Purpose:** Allow Redshift/Spectrum role in another account to use CMK for S3 SSE-KMS.

**Command:**

```bash
aws kms create-grant \
  --key-id alias/data-lake-prod \
  --grantee-principal arn:aws:iam::987654321098:role/RedshiftSpectrumRole \
  --operations Decrypt DescribeKey \
  --name redshift-spectrum-cross-account
```

---

### Put Key Policy

**Purpose:** Define who can administer and use the key.

**Command:**

```bash
aws kms put-key-policy \
  --key-id alias/data-lake-prod \
  --policy-name default \
  --policy file://data-lake-key-policy.json
```

**Example policy snippet (`data-lake-key-policy.json`):**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EnableRootPermissions",
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::123456789012:root"},
      "Action": "kms:*",
      "Resource": "*"
    },
    {
      "Sid": "AllowGlueETLUse",
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::123456789012:role/GlueETLRole"},
      "Action": ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"],
      "Resource": "*"
    },
    {
      "Sid": "AllowS3ServiceUse",
      "Effect": "Allow",
      "Principal": {"Service": "s3.amazonaws.com"},
      "Action": ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"],
      "Resource": "*",
      "Condition": {
        "StringEquals": {"kms:ViaService": "s3.us-east-1.amazonaws.com"}
      }
    }
  ]
}
```

---

### Schedule Key Deletion

**Command:**

```bash
aws kms schedule-key-deletion \
  --key-id 12345678-1234-1234-1234-123456789012 \
  --pending-window-in-days 30
```

---

### Cancel Key Deletion

**Command:**

```bash
aws kms cancel-key-deletion --key-id 12345678-1234-1234-1234-123456789012
```

---

## Advanced Commands

### Re-Encrypt to New CMK (Migration)

```bash
aws kms re-encrypt \
  --ciphertext-blob fileb://encrypted-token.bin \
  --source-key-id alias/data-lake-prod \
  --destination-key-id alias/data-lake-prod-v2 \
  --output text --query CiphertextBlob | base64 -d > encrypted-token-v2.bin
```

### List Grants on Key

```bash
aws kms list-grants \
  --key-id alias/data-lake-prod \
  --query 'Grants[].{Id:GrantId,Principal:GranteePrincipal,Ops:Operations}' \
  --output table
```

### Retire Grant

```bash
aws kms retire-grant --grant-id "<grant-id>" --key-id alias/data-lake-prod
```

### Connect Custom Key Store (CloudHSM)

```bash
aws kms connect-custom-key-store --custom-key-store-id cks-01234567890123456789012
```

### Filter Keys by Tag

```bash
aws kms list-resource-tags \
  --key-id alias/data-lake-prod \
  --output table
```

### Get Public Key (Asymmetric Keys)

```bash
aws kms get-public-key --key-id alias/pipeline-signing-key --output text --query PublicKey | base64 -d > public.key
```

---

## Python (Boto3) Examples

### Basic — Generate Data Key

```python
import base64

import boto3

kms = boto3.client("kms")
resp = kms.generate_data_key(KeyId="alias/data-lake-prod", KeySpec="AES_256")
plaintext_key = resp["Plaintext"]  # use for local encryption, then discard
encrypted_key = resp["CiphertextBlob"]  # store with encrypted artifact
```

See [kms_python_examples.md](kms_python_examples.md) for envelope encryption and S3 integration.

---

## Security Considerations

- Use **customer managed keys (CMK)** for data lake buckets requiring audit and cross-account access.
- Apply **least privilege** in key policies — separate admin (`kms:Create*`) from use (`kms:Decrypt`, `kms:GenerateDataKey`).
- Enable **automatic rotation** on CMKs encrypting production data.
- Monitor **`kms:DisableKey`** and **`kms:ScheduleKeyDeletion`** via CloudTrail alarms.
- Use **grants** for temporary cross-account access instead of broad key policy changes.
- Never log **plaintext** data keys or decrypted values.
- Restrict **`kms:Decrypt`** to specific IAM roles (Glue, Lambda, Redshift) via key policy conditions.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `AccessDeniedException` on S3 PUT | Role lacks `kms:GenerateDataKey` | Add encrypt/decrypt permissions on CMK for caller role |
| `KMSInvalidStateException` | Key disabled or pending deletion | `enable-key` or `cancel-key-deletion` |
| `IncorrectKeyException` | Wrong key used to decrypt | Verify bucket default encryption key matches object metadata |
| Cross-account S3 access fails | Key policy missing external account | Add principal or grant for external role |
| High KMS API costs | Per-object SSE-KMS on small files | Batch objects; use S3 Bucket Keys; consolidate files |
| `InvalidCiphertextException` | Corrupted blob or wrong region | Ensure ciphertext not modified; use same region key |

---

## Best Practices

- Create **one CMK per data domain** or environment (`alias/data-lake-prod`, `alias/redshift-prod`).
- Enable **S3 Bucket Keys** to reduce KMS API costs on high-throughput buckets.
- Document key policy changes in IaC (CloudFormation/Terraform) — avoid console-only edits.
- Use **aliases** in bucket policies and IAM — simplifies key rotation/migration.
- Tag CMKs with `Environment`, `DataClassification`, `Owner` for cost and compliance reporting.
- Test **decrypt access** from each consumer role (Glue, Redshift Spectrum, Athena) after key creation.
- Plan **key migration** with `re-encrypt` or S3 copy to new bucket when retiring CMKs.
- Enable **CloudTrail** management and data events for all `kms.amazonaws.com` API calls.
